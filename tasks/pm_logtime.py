import asyncio
from datetime import datetime, date
import structlog
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from services.email_service import send_email_async
from apps.api.services.connectors_service import _run_sync_task

log = structlog.get_logger()

async def check_daily_logtime(target_date: date | None = None, ctx=None):
    """
    Worker task: Kiểm tra log time Jira hàng ngày và gửi nhắc nhở.
    """
    if target_date is None:
        target_date = date.today()
        
    log.info("pm_logtime.check.started", target_date=target_date.isoformat())
    
    try:
        async with AsyncSessionLocal() as session:
            # 1. Tìm tất cả các dự án Jira có trong hệ thống (dựa trên Groups)
            project_groups_res = await session.execute(
                text("SELECT id FROM groups WHERE id LIKE 'group_jira_project_%'")
            )
            project_group_ids = [row[0] for row in project_groups_res.fetchall()]
            project_keys = [gid.replace("group_jira_project_", "").upper() for gid in project_group_ids]
            
            if not project_keys:
                log.warning("pm_logtime.check.no_projects_found")
                return

            log.info("pm_logtime.check.projects_to_process", count=len(project_keys))

            # 2. Force Sync Jira sơ bộ (Tùy chọn, ở đây ta sync theo project nếu cần)
            res_connectors = await session.execute(text("SELECT instance_id FROM connectors WHERE type = 'jira' AND status = 'ready'"))
            jira_instances = [row[0] for row in res_connectors.fetchall()]
            for inst_id in jira_instances:
                try:
                    await _run_sync_task("jira", inst_id, incremental=True)
                except Exception as sync_err:
                    log.error("pm_logtime.sync_failed", instance_id=inst_id, error=str(sync_err))

            # 3. Lặp qua từng dự án để kiểm tra và gửi báo cáo cô lập
            for pk in project_keys:
                pk_lower = pk.lower()
                log.info("pm_logtime.process_project", project=pk)
                
                # A. Lấy danh sách thành viên thuộc dự án này
                # (Bao gồm dev_qa, ba_sa, pm_po nằm trong group dự án)
                members_query = text("""
                    SELECT DISTINCT u.email, u.display_name, u.role 
                    FROM users u
                    JOIN user_groups ug ON u.id = ug.user_id
                    JOIN groups g ON ug.group_id = g.id
                    WHERE u.is_active = true 
                      AND u.role IN ('dev_qa', 'ba_sa', 'pm_po')
                      AND (g.id = :g1 OR g.id = :g2)
                """)
                members_res = await session.execute(members_query, {
                    "g1": f"group_jira_project_{pk_lower}",
                    "g2": f"group_project_{pk_lower}"
                })
                project_members = [dict(row) for row in members_res.mappings().all()]
                
                if not project_members:
                    continue

                # B. Lấy danh sách PM của dự án này (Để gửi báo cáo tổng hợp)
                pms = [m["email"] for m in project_members if m["role"] == "pm_po" and m["email"]]
                
                # C. Lấy log time của dự án này trong ngày target_date
                worklog_query = text("""
                    SELECT 
                        w->>'author' as author_name,
                        w->>'author_email' as author_email,
                        SUM(CAST(COALESCE(w->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
                    FROM documents,
                         jsonb_array_elements(CASE WHEN jsonb_typeof((metadata->'worklog')::jsonb) = 'array' THEN (metadata->'worklog')::jsonb ELSE '[]'::jsonb END) w
                    WHERE source = 'jira' 
                      AND metadata->>'project_key' = :pk
                      AND CAST(w->>'started' AS DATE) = :t_date
                    GROUP BY 1, 2
                """)
                worklog_res = await session.execute(worklog_query, {"pk": pk, "t_date": target_date})
                worklogs = worklog_res.mappings().all()
                
                logged_users = {}
                for wl in worklogs:
                    if wl["author_email"]: logged_users[wl["author_email"].lower()] = wl["seconds"]
                    if wl["author_name"]: logged_users[wl["author_name"].lower()] = wl["seconds"]

                # D. Phân loại ai chưa log
                missed_users = []
                logged_summary = []
                for user in project_members:
                    email = (user["email"] or "").lower()
                    name = (user["display_name"] or "").lower()
                    
                    seconds_logged = logged_users.get(email, logged_users.get(name, 0))
                    hours = round(seconds_logged / 3600.0, 1)
                    
                    u_info = {"email": user["email"], "display_name": user["display_name"], "hours": hours}
                    if hours == 0:
                        missed_users.append(u_info)
                    else:
                        logged_summary.append(u_info)

                # E. Gửi nhắc nhở cá nhân (Chỉ cho những người thuộc dự án này)
                for user in missed_users:
                    if not user["email"]: continue
                    subject = f"[Dự án {pk}] Nhắc nhở log time Jira - {target_date.strftime('%d/%m/%Y')}"
                    body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #e11d48;">Nhắc nhở Log Time - Dự án {pk}</h2>
                        <p>Chào <b>{user['display_name']}</b>,</p>
                        <p>Bạn <b>chưa log time</b> cho dự án <b>{pk}</b> trong ngày hôm nay.</p>
                        <p>Vui lòng cập nhật sớm để PM nắm được tiến độ nhé.</p>
                        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                        <p style="font-size: 0.85em; color: #94a3b8;">Đây là thông báo tự động từ Knowledge Platform.</p>
                    </body>
                    </html>
                    """
                    await send_email_async(to_email=user["email"], subject=subject, body=body, is_html=True)

                # F. Gửi báo cáo tổng hợp cho PM của dự án (Cô lập hoàn toàn)
                if pms and (missed_users or logged_summary):
                    report_html = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #2563eb;">Báo cáo Log Time Dự án {pk}</h2>
                        <p>Ngày: <b>{target_date.strftime('%d/%m/%Y')}</b></p>
                        <p>Đã log: <b style="color: #16a34a;">{len(logged_summary)}</b> | Chưa log: <b style="color: #dc2626;">{len(missed_users)}</b></p>
                        
                        <h3>Danh sách chưa log:</h3>
                        <ul>
                            {"".join([f"<li>{u['display_name']} ({u['email']})</li>" for u in missed_users]) if missed_users else "<li><i>Tất cả đã log time!</i></li>"}
                        </ul>
                        
                        <h3>Chi tiết giờ làm việc:</h3>
                        <table border="1" style="border-collapse: collapse; width: 100%;">
                            <tr style="background-color: #f8fafc;">
                                <th style="padding: 8px;">Thành viên</th>
                                <th style="padding: 8px;">Số giờ log (Dự án {pk})</th>
                            </tr>
                            {"".join([f"<tr><td style='padding:8px;'>{u['display_name']}</td><td style='padding:8px; text-align:center;'>{u['hours']}h</td></tr>" for u in logged_summary])}
                        </table>
                    </body>
                    </html>
                    """
                    await send_email_async(
                        to_email=pms, 
                        subject=f"[Báo cáo] Log time dự án {pk} - {target_date.strftime('%d/%m/%Y')}", 
                        body=report_html, 
                        is_html=True
                    )
                    log.info("pm_logtime.project_report_sent", project=pk, pms_count=len(pms))

        log.info("pm_logtime.check.completed")
    except Exception as e:
        log.error("pm_logtime.check.failed", error=str(e))
        import traceback
        log.error(traceback.format_exc())
