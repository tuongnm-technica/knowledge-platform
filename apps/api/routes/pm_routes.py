from fastapi import APIRouter, Depends, HTTPException
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import json
from pydantic import BaseModel
from services.llm_service import LLMService

from apps.api.auth.dependencies import CurrentUser, get_current_user
from apps.api.auth.access_control import validate_project_access, get_accessible_projects
from storage.db.db import get_db
from connectors.jira.jira_client import JiraClient

router = APIRouter(prefix="/pm", tags=["pm_dashboard"])
log = structlog.get_logger()

@router.get("/projects")
async def get_pm_projects(
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        # Check permission level
        client = JiraClient()
        if user.is_admin:
            projects_data = client.get_projects()
            projects = [
                {
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "avatar": p.get("avatarUrls", {}).get("48x48")
                } 
                for p in projects_data
            ]
        else:
            # Chỉ lấy các project mà user có group tương ứng
            permitted_keys = get_accessible_projects(user)
            if not permitted_keys:
                return {"projects": []}
                
            all_p = client.get_projects()
            projects = [
                {
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "avatar": p.get("avatarUrls", {}).get("48x48")
                } 
                for p in all_p if p.get("key") in permitted_keys
            ]
        return {"projects": projects}
    except Exception as e:
        # Fallback to DB if live Jira connection fails
        if user.is_admin:
            res = await session.execute(text("SELECT DISTINCT project_key as key FROM pm_metrics_by_project"))
        else:
            permitted_keys = get_accessible_projects(user)
            res = await session.execute(
                text("SELECT DISTINCT project_key as key FROM pm_metrics_by_project WHERE project_key = ANY(:keys)"),
                {"keys": permitted_keys}
            )
        projects = [{"key": row[0], "name": row[0]} for row in res.fetchall()]
        return {"projects": projects}


@router.get("/dashboard/stats")
async def get_pm_dashboard_stats(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not project_key or project_key.strip() == "":
        project_key = None
    else:
        project_key = project_key.strip().replace("[", "").replace("]", "")

    # Security Check from the Root
    await validate_project_access(project_key, user)

    # Fetching metrics from pm_metrics_daily and pm_project_insights
    if project_key:
        query_metrics = text("""
            SELECT 
                todo_count, in_progress_count, done_count, high_priority_count
            FROM pm_metrics_daily
            WHERE (project_key ILIKE '%' || CAST(:p AS TEXT) || '%' OR CAST(:p AS TEXT) || '%' ILIKE '%' || project_key || '%')
            ORDER BY date DESC LIMIT 1
        """)
        query_insights = text("""
            SELECT velocity_weekly, risk_score, health_status, insight
            FROM pm_metrics_by_project
            WHERE (project_key = CAST(:p AS TEXT))
            ORDER BY updated_at DESC LIMIT 1
        """)
    else:
        # Global View (Admin only usually, or union of permitted)
        # For simple root security, if no project_key, we might return sum of permitted
        permitted_keys = get_accessible_projects(user)
        
        query_metrics = text("""
            WITH latest_dates AS (
                SELECT project_key, MAX(date) as max_date
                FROM pm_metrics_daily
                WHERE (:is_admin OR project_key = ANY(:keys))
                GROUP BY project_key
            )
            SELECT 
                SUM(m.todo_count) as todo_count, 
                SUM(m.in_progress_count) as in_progress_count, 
                SUM(m.done_count) as done_count, 
                SUM(m.high_priority_count) as high_priority_count
            FROM pm_metrics_daily m
            JOIN latest_dates ld ON m.project_key = ld.project_key AND m.date = ld.max_date
        """)
        query_insights = text("""
            SELECT 
                AVG(velocity_weekly) as velocity_weekly, 
                AVG(risk_score) as risk_score, 
                'overview' as health_status, 
                'Global overview of your permitted projects' as insight
            FROM pm_metrics_by_project
            WHERE (:is_admin OR project_key = ANY(:keys))
        """)
    
    params = {"p": project_key, "is_admin": user.is_admin, "keys": get_accessible_projects(user)}
    res_metrics = await session.execute(query_metrics, params)
    stats_row = res_metrics.fetchone()
    res_insights = await session.execute(query_insights, params)
    insights_row = res_insights.fetchone()
    
    # [LIVE FALLBACK] If no daily metrics found or they are all NULL, compute live from documents table
    is_empty = not stats_row or all(v is None for v in stats_row)
    
    if is_empty:
        live_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'to do' OR (metadata)::jsonb->>'status' ILIKE 'open') as todo,
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'in progress' OR (metadata)::jsonb->>'status' ILIKE 'in progress' OR (metadata)::jsonb->>'status' ILIKE 'doing') as wip,
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'done' OR (metadata)::jsonb->>'status' ILIKE 'resolved' OR (metadata)::jsonb->>'status' ILIKE 'closed' OR (metadata)::jsonb->>'status' ILIKE 'done') as done,
                COUNT(*) FILTER (WHERE ((metadata)::jsonb->>'priority' ILIKE 'high' OR (metadata)::jsonb->>'priority' ILIKE 'critical' OR (metadata)::jsonb->>'priority' ILIKE 'highest')) as high
            FROM documents
            WHERE source = 'jira' 
              AND (
                  (:is_admin OR metadata->>'project_key' = ANY(:keys))
              )
              AND (
                  CAST(:p AS TEXT) IS NULL 
                  OR metadata->>'project_key' = CAST(:p AS TEXT)
              )
        """)
        res_live = await session.execute(live_query, params)
        live_stats = res_live.fetchone()
        stats = {
            "todo_count": live_stats[0] or 0,
            "in_progress_count": live_stats[1] or 0,
            "done_count": live_stats[2] or 0,
            "high_priority_count": live_stats[3] or 0
        }
    else:
        stats = {
            "todo_count": stats_row[0] or 0,
            "in_progress_count": stats_row[1] or 0,
            "done_count": stats_row[2] or 0,
            "high_priority_count": stats_row[3] or 0
        }
    
    # Standardize stats for frontend
    todo = stats.get("todo_count", 0)
    wip = stats.get("in_progress_count", 0)
    done = stats.get("done_count", 0)
    high = stats.get("high_priority_count", 0)
    total = todo + wip + done
    rate = round((done / total * 100), 1) if total > 0 else 0
    
    formatted_stats = {
        "todo_issues": todo,
        "in_progress_issues": wip,
        "done_issues": done,
        "high_priority_issues": high,
        "total_issues": total,
        "completion_rate": rate
    }

    # Optional: Merge project insights if available
    p_res = await session.execute(query_insights, params)
    p_metrics = p_res.mappings().first()
    if p_metrics:
        formatted_stats.update({
            "velocity_weekly": round(p_metrics["velocity_weekly"] or 0, 1),
            "risk_score": round(p_metrics["risk_score"] or 0, 1),
            "health_status": p_metrics["health_status"]
        })
    
    return formatted_stats
    
@router.get("/dashboard/risks")
async def get_pm_risks(
    project_key: Optional[str] = None,
    limit: int = 5,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        title, content, created_at
    FROM doc_drafts
    WHERE doc_type = 'pm_risk_report'
    """
    
    params = {}
    if project_key:
        query += " AND title ILIKE :p"
        params["p"] = f"%{project_key}%"
    else:
        # If no project_key, filter by what's permitted
        permitted_keys = get_accessible_projects(user)
        if not user.is_admin:
            query += " AND (FALSE " # build a chain of ORs for permitted projects in title
            for i, pk in enumerate(permitted_keys):
                query += f" OR title ILIKE :p{i}"
                params[f"p{i}"] = f"%{pk}%"
            query += ")"
        
    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    risks = []
    for r in rows:
        risks.append({
            "title": r["title"],
            "summary": r["content"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None
        })
        
    # If no AI reports generated yet, send dummy data just for the UI
    if not risks:
        risks = [
            {
                "title": "Chưa có báo cáo AI",
                "summary": "Hệ thống tự động (PM Digest) chưa chạy cho dự án này. Báo cáo sẽ được tạo vào 8:00 AM Thứ Hai và Thứ Năm.",
                "created_at": None
            }
        ]
        
    return {"risks": risks}

@router.get("/dashboard/workload")
async def get_pm_workload(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = "SELECT user_id, display_name, project_key, todo_count, in_progress_count, done_count FROM pm_metrics_by_user"
    params = {}
    if project_key:
        query += " WHERE project_key = :p"
        params = {"p": project_key}
    else:
        # Filter global view by permitted projects
        if not user.is_admin:
            permitted_keys = get_accessible_projects(user)
            query += " WHERE project_key = ANY(:keys)"
            params = {"keys": permitted_keys}
        
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    workload = {}
    for r in rows:
        name = r["display_name"] or r["user_id"]
        if name not in workload:
            workload[name] = {"to do": 0, "in progress": 0, "done": 0}
        workload[name]["to do"] += r["todo_count"]
        workload[name]["in progress"] += r["in_progress_count"]
        workload[name]["done"] += r["done_count"]
            
    return {"workload": workload}

@router.get("/dashboard/logtime")
async def get_pm_logtime(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
        SELECT 
            metadata->'assignee'->>'displayName' as user_name,
            SUM(CAST(COALESCE(metadata->'timetracking'->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
        FROM documents
        WHERE source = 'jira' 
          AND (
              CAST(:p AS TEXT) IS NULL
              OR metadata->>'project_key' = CAST(:p AS TEXT)
          )
    """
    
    params = {"p": project_key}
    if not user.is_admin and not project_key:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += """
        GROUP BY 1
        HAVING SUM(CAST(COALESCE(metadata->'timetracking'->>'timeSpentSeconds', '0') AS INTEGER)) > 0
        ORDER BY seconds DESC
    """
    
    res = await session.execute(text(query), params)
    rows = res.fetchall()
    
    logtime = []
    for r in rows:
        logtime.append({
            "user": r[0],
            "hours": round(r[1] / 3600.0, 1)
        })
        
    return {"logtime": logtime}

@router.get("/dashboard/logtime-trend")
async def get_pm_logtime_trend(
    project_key: Optional[str] = None,
    days: int = 250,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    # Security Check
    await validate_project_access(project_key, user)

    query = """
        SELECT 
            CAST(w->>'started' AS DATE) as log_date,
            w->>'author' as user_name,
            SUM(CAST(COALESCE(w->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
        FROM documents,
             jsonb_array_elements(CASE WHEN jsonb_typeof((metadata->'worklog')::jsonb) = 'array' THEN (metadata->'worklog')::jsonb ELSE '[]'::jsonb END) w
        WHERE source = 'jira' 
          AND (w->>'started') IS NOT NULL
          AND CAST(w->>'started' AS DATE) >= CURRENT_DATE - INTERVAL '1 day' * :days
    """
    
    params = {"p": project_key, "days": days}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += """
        GROUP BY 1, 2
        ORDER BY 1 ASC, 3 DESC
    """
    
    res = await session.execute(text(query), params)
    rows = res.fetchall()
    
    trend = []
    for r in rows:
        trend.append({
            "date": r[0].isoformat() if r[0] else None,
            "user": r[1],
            "hours": round(r[2] / 3600.0, 1)
        })
        
    return {"trend": trend}


@router.get("/dashboard/stale")
async def get_pm_stale_tasks(
    project_key: Optional[str] = None,
    days: int = 3,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        source_id as key, title, 
        metadata->>'status' as status, 
        metadata->'assignee'->>'displayName' as assignee, 
        updated_at
    FROM documents 
    WHERE source = 'jira' 
      AND metadata->>'statusCategory' = 'in progress'
      AND updated_at < NOW() - INTERVAL '1 day' * :d
    """
    params = {"p": project_key, "d": days}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += " ORDER BY updated_at ASC LIMIT 50"
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    return {"tasks": [dict(r) for r in rows]}
    
@router.post("/dashboard/refresh-ai")
async def refresh_pm_ai_analysis(
    project_key: str,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Endpoint để PM chủ động kích hoạt AI phân tích rủi ro ngay lập tức.
    Đẩy 1 job vào hàng chờ arq:ai.
    """
    if user.role not in ["pm_po", "system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Only PMs and Admins can refresh AI analysis")
        
    try:
        from arq_worker import REDIS_URL
        from arq import create_pool
        from arq.connections import RedisSettings
        
        # Security Check
        await validate_project_access(project_key, user)

        # Kiểm tra xem dự án có dữ liệu Jira không
        res = await session.execute(
            text("""SELECT COUNT(*) FROM documents WHERE source = 'jira' AND metadata->>'project_key' = :p"""),
            {"p": project_key}
        )

        count = res.scalar() or 0
        if count == 0:
            raise HTTPException(status_code=404, detail=f"No Jira data found for project {project_key}")

        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        # Enqueue job cụ thể cho project này
        await pool.enqueue_job("generate_pm_digest_job_proxy", project_keys=[project_key], _queue_name="arq:ai")
        
        return {"status": "enqueued", "project": project_key, "message": "AI analysis task has been started. Please refresh after 10-20 seconds."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("pm_routes.refresh_ai.failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dashboard/test-logtime-check")
async def test_pm_logtime_check(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Endpoint để PM/Admin kích hoạt kiểm tra log-time ngay lập tức (phục vụ testing).
    """
    if user.role not in ["pm_po", "system_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Only PMs and Admins can trigger log-time checks")
        
    try:
        from arq_worker import REDIS_URL
        from arq import create_pool
        from arq.connections import RedisSettings
        
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        # Enqueue job kiểm tra
        await pool.enqueue_job("check_daily_logtime", _queue_name="arq:ai")
        
        return {"status": "enqueued", "message": "Log-time check job has been enqueued to arq:ai. Check worker logs and your email (if you are in the list)."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/burnup")
async def get_pm_burnup(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        DATE(updated_at) as done_date,
        COUNT(id) as count
    FROM documents 
    WHERE source = 'jira' 
      AND (metadata)::jsonb->>'statusCategory' = 'done'
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += " GROUP BY DATE(updated_at) ORDER BY DATE(updated_at) ASC LIMIT 30"
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    # Calculate cumulative (Burnup)
    burnup_data = []
    cumulative = 0
    for r in rows:
        cumulative += r["count"]
        burnup_data.append({
            "date": r["done_date"].isoformat() if r["done_date"] else None,
            "daily_completed": r["count"],
            "cumulative": cumulative
        })
        
    return {"burnup": burnup_data}

@router.get("/dashboard/cfd")
async def get_pm_cfd(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    # Simulated CFD from current Snapshot DB
    query = """
    SELECT 
        DATE(created_at) as created_date,
        COUNT(id) as total_entered
    FROM documents 
    WHERE source = 'jira'
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys
        
    query += " GROUP BY DATE(created_at) ORDER BY DATE(created_at) ASC"
    
    created_res = await session.execute(text(query), params)
    
    # Same for done
    query_done = """
    SELECT 
        DATE(updated_at) as resolved_date,
        COUNT(id) as total_resolved
    FROM documents 
    WHERE source = 'jira' AND (metadata)::jsonb->>'statusCategory' = 'done'
    """
    if project_key:
        query_done += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        query_done += " AND metadata->>'project_key' = ANY(:keys)"
        
    query_done += " GROUP BY DATE(updated_at) ORDER BY DATE(updated_at) ASC"
    
    resolved_res = await session.execute(text(query_done), params)
    
    created_rows = created_res.mappings().fetchall()
    resolved_rows = resolved_res.mappings().fetchall()
    
    timeline = {}
    for r in created_rows:
        d = r["created_date"].isoformat() if r["created_date"] else "unknown"
        if d not in timeline:
             timeline[d] = {"entered": 0, "resolved": 0}
        timeline[d]["entered"] += r["total_entered"]
        
    for r in resolved_rows:
        d = r["resolved_date"].isoformat() if r["resolved_date"] else "unknown"
        if d not in timeline:
             timeline[d] = {"entered": 0, "resolved": 0}
        timeline[d]["resolved"] += r["total_resolved"]
        
    dates = sorted(list(timeline.keys()))
    cfd_data = []
    cum_entered = 0
    cum_resolved = 0
    
    for d in dates:
        if d == "unknown": continue
        cum_entered += timeline[d]["entered"]
        cum_resolved += timeline[d]["resolved"]
        
        # Calculate ToDo + InProgress loosely as entered - resolved
        wip = cum_entered - cum_resolved
        if wip < 0: wip = 0
        
        cfd_data.append({
            "date": d,
            "done": cum_resolved,
            "wip": wip,  # To do + In Progress
            "total": cum_entered
        })
        
    return {"cfd": cfd_data[-30:]} # Last 30 points

@router.get("/dashboard/lead-time")
async def get_pm_lead_time(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        DATE(updated_at) as done_date,
        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/86400) as daily_avg_lead_time
    FROM documents 
    WHERE source = 'jira' 
      AND (metadata)::jsonb->>'statusCategory' = 'done'
      AND updated_at IS NOT NULL
      AND created_at IS NOT NULL
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += " GROUP BY DATE(updated_at) ORDER BY DATE(updated_at) ASC LIMIT 30"
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    overall_avg = 0
    trend = []
    total_days = 0
    count = 0
    for r in rows:
        val = float(r["daily_avg_lead_time"] or 0)
        total_days += val
        count += 1
        trend.append({
            "date": r["done_date"].isoformat() if r["done_date"] else None,
            "avg_lead_time_days": round(val, 2)
        })
        
    if count > 0:
        overall_avg = round(total_days / count, 2)
        
    return {"overall_avg_lead_time_days": overall_avg, "trend": trend}

@router.get("/dashboard/issue-types")
async def get_pm_issue_types(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        COALESCE(metadata->>'issue_type', 'Unknown') as issue_type,
        COUNT(id) as count
    FROM documents 
    WHERE source = 'jira'
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += " GROUP BY COALESCE(metadata->>'issue_type', 'Unknown') ORDER BY count DESC"
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    res_data = [{"type": r["issue_type"], "count": r["count"]} for r in rows]
    return {"issue_types": res_data}

@router.get("/dashboard/epics")
async def get_pm_epics(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    # Fetch Epics
    query = """
    SELECT 
        source_id as key,
        title,
        metadata->>'status' as status_name,
        metadata->>'statusCategory' as status_category,
        updated_at,
        url
    FROM documents
    WHERE source = 'jira'
      AND metadata->>'issue_type' = 'Epic'
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys

    query += " ORDER BY updated_at DESC LIMIT 20"
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    epics = []
    for r in rows:
        cat = r["status_category"] or "to do"
        progress = 100 if cat.lower() == 'done' else (50 if cat.lower() in ['in progress', 'indeterminate'] else 0)
        epics.append({
            "key": r["key"],
            "title": r["title"],
            "status": r["status_name"],
            "progress": progress,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "url": r["url"]
        })
        
    return {"epics": epics}

@router.get("/dashboard/retrospective")
async def get_pm_retrospective(
    project_key: Optional[str] = None,
    limit: int = 2,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security Check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        title, content, created_at
    FROM doc_drafts
    WHERE doc_type = 'pm_sprint_retrospective'
    """
    params = {"limit": limit, "p": project_key}
    if project_key:
        query += " AND title ILIKE :p" # retrospective usually have project_key in title
        params["p"] = f"%{project_key}%"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND (FALSE "
        for i, pk in enumerate(permitted_keys):
            query += f" OR title ILIKE :p{i}"
            params[f"p{i}"] = f"%{pk}%"
        query += ")"
        
    query += " ORDER BY created_at DESC LIMIT :limit"
    
    res = await session.execute(text(query), params)
    rows = res.mappings().fetchall()
    
    reports = []
    for r in rows:
        reports.append({
            "title": r["title"],
            "summary": r["content"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None
        })
        
    if not reports:
        reports = [
            {
                "title": "Chưa có báo cáo AI Retrospective",
                "summary": "AI Retrospective được sinh ra tự động vào cuối mỗi Sprint (TBD).",
                "created_at": None
            }
        ]
        
    return {"retrospectives": reports}


class CustomReportRequest(BaseModel):
    project_key: str
    prompt: Optional[str] = None
    action_type: Optional[str] = "custom" # bottleneck, risk, velocity, workload, custom

@router.post("/dashboard/custom-report")
async def generate_pm_custom_report(
    req: CustomReportRequest,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    project_key = req.project_key.strip().replace("[", "").replace("]", "")
    prompt = (req.prompt or "").strip()
    action = req.action_type or "custom"
    
    if not project_key:
        raise HTTPException(status_code=400, detail="Missing project_key")
        
    # Mapping quick actions to prompt templates
    action_map = {
        "bottleneck": "Phân tích các điểm nghẽn (bottlenecks) hiện tại. Task nào đang bị tắc nghẽn lâu nhất? Team nào đang quá tải?",
        "risk": "Đánh giá các rủi ro quan trọng ảnh hưởng đến tiến độ dự án. Xác định các task có nguy cơ trễ hạn cao.",
        "velocity": "Phân tích xu hướng Velocity (tốc độ hoàn thành). So sánh với các tuần trước và dự báo khả năng hoàn thành mục tiêu.",
        "workload": "Kiểm toán khối lượng công việc theo từng thành viên. Ai đang rảnh, ai đang quá tải? Đề xuất phân bổ lại.",
        "custom": prompt
    }
    final_prompt = action_map.get(action, prompt)
    
    # 0. Permission check
    await validate_project_access(project_key, user)

    # 1. Fetch current status metrics
    metrics_query = """
    SELECT 
        p.velocity_weekly, p.velocity_delta_pct, p.risk_score, p.health_status,
        d.todo_count, d.in_progress_count, d.done_count
    FROM pm_metrics_by_project p
    JOIN pm_metrics_daily d ON d.project_key = p.project_key
    WHERE p.project_key = :p
    ORDER BY d.date DESC LIMIT 1
    """
    m_res = await session.execute(text(metrics_query), {"p": project_key})
    m = m_res.mappings().first() or {}
    
    # 2. Fetch Top 10 Stale Issues (Critical Context)
    stale_query = """
    SELECT source_id as key, title, metadata->'assignee'->>'displayName' as assignee, updated_at
    FROM documents 
    WHERE source = 'jira' 
      AND metadata->>'project_key' = :p
      AND metadata->>'statusCategory' = 'in progress'
      AND updated_at < NOW() - INTERVAL '3 days'
    ORDER BY updated_at ASC LIMIT 10
    """
    s_res = await session.execute(text(stale_query), {"p": project_key})
    stale_issues = s_res.mappings().all()
    stale_str = "\n".join([f"- [{i['key']}] {i['title']} (Assignee: {i['assignee']}, Last Updated: {i['updated_at']})" for i in stale_issues])

    # 3. Fetch Recent Bottleneck (WIP issues)
    wip_query = text("""
        SELECT source_id as key, title, metadata->'assignee'->>'displayName' as assignee, metadata->>'status' as status
        FROM documents 
        WHERE source = 'jira' 
          AND metadata->>'project_key' = :p
          AND metadata->>'statusCategory' = 'in progress'
        ORDER BY updated_at DESC LIMIT 10
    """)
    w_res = await session.execute(wip_query, {"p": project_key})
    wip_items = w_res.mappings().all()
    wip_str = "\n".join([f"- [{i['key']}] {i['title']} ({i['status']})" for i in wip_items])

    metrics_summary = f"""
    THỐNG KÊ HIỆN TẠI ({project_key}):
    - Velocity tuần này: {m.get('velocity_weekly', 0)} task
    - So với tuần trước: {m.get('velocity_delta_pct', 0)}%
    - Chỉ số rủi ro: {m.get('risk_score', 0)}/100 (Trạng thái: {m.get('health_status', 'N/A')})
    - Phân bổ: ToDo({m.get('todo_count',0)}), InProgress({m.get('in_progress_count',0)}), Done({m.get('done_count',0)})

    DANH SÁCH TASK BỊ TREO (>3 ngày):
    {stale_str if stale_str else "Không có task nào bị treo."}

    TASK ĐANG THỰC HIỆN (WIP):
    {wip_str if wip_str else "Chưa có dữ liệu WIP."}
    """

    system_prompt = f"""Bạn là một Chuyên gia Quản lý Dự án AI Strategic Insights. Nhiệm vụ của bạn là phân tích dữ liệu Jira và đưa ra báo cáo QUYẾT ĐỊNH (Decision-Support) cho PM.

QUY TẮC PHẢN HỒI (BẮT BUỘC):
1. CẤU TRÚC BÁO CÁO: Luôn bắt đầu bằng phần tóm tắt cực ngắn gọn (Summary), sau đó là bảng Đề xuất hành động (Action Items), cuối cùng là phần Giải trình (Evidence).
2. TÍNH CHÍNH XÁC: Bạn phải trích dẫn mã ISSUE KEY cụ thể (ví dụ: PROJ-123) khi nói về rủi ro hoặc rào cản. Không nói chung chung.
3. ĐỀ XUẤT HÀNH ĐỘNG: Mỗi hành động phải có độ ưu tiên (High/Med/Low) và đề xuất người phụ trách (Owner) dựa trên dữ liệu Assignee.
4. TÍNH CHUYÊN NGHIỆP: Sử dụng ngôn ngữ PM sắc bén (ví dụ: "Bottleneck", "Risk Mitigation", "Log-Time Audit").
5. ĐỊNH DẠNG: Trả về Markdown chuyên nghiệp. 
6. BIỂU ĐỒ: Khi cần minh họa dữ liệu (phân bổ Assignee, rủi ro, Log-time theo User, v.v.), hãy xuất mã biểu đồ theo format:
```
[[CHART:{{ "type":"pie|bar|line", "title": "...", "labels": [], "data": [] }}]]
```
7. SUMMARY JSON: Cuối cùng, hãy luôn xuất một khối JSON nhỏ chứa thông tin tóm tắt.

DỮ LIỆU BỔ SUNG:
Mỗi Issue hiện có thêm trường `timetracking` (chứa `originalEstimate`, `timeSpent`) và `worklog` (danh sách các lần log thời gian chi tiết gồm: `author`, `timeSpent`, `started`). Hãy sử dụng dữ liệu này nếu User yêu cầu báo cáo về Log-time hoặc Effort.

DỮ LIỆU DỰ ÁN:
{metrics_summary}
"""

    llm = LLMService(task_type="pm_report")
    try:
        reply = await llm.chat(system=system_prompt, user=f"Yêu cầu PM: {final_prompt}", max_tokens=2000)
        return {"report": reply, "project": project_key, "action": action}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")


@router.get("/dashboard/at-risk")
async def get_at_risk_projects(
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Filter by permitted projects
    permitted_keys = get_accessible_projects(user)
    
    query = """
        SELECT * FROM pm_metrics_by_project 
        WHERE health_status != 'healthy' 
        AND (:is_admin OR project_key = ANY(:keys))
        ORDER BY risk_score DESC LIMIT 5
    """
    res = await session.execute(text(query), {"is_admin": user.is_admin, "keys": permitted_keys})
    return {"projects": [dict(r) for r in res.mappings().fetchall()]}


@router.get("/dashboard/details")
async def get_pm_drilldown(
    metric: str,
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Security check
    await validate_project_access(project_key, user)

    query = """
    SELECT 
        source_id as key, title, 
        metadata->>'status' as status, 
        metadata->'assignee'->>'displayName' as assignee, 
        url
    FROM documents
    WHERE source = 'jira'
    """
    params = {"p": project_key}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
    elif not user.is_admin:
        permitted_keys = get_accessible_projects(user)
        query += " AND metadata->>'project_key' = ANY(:keys)"
        params["keys"] = permitted_keys
        
    if metric == "high_priority":
        query += " AND metadata->>'priority' IN ('High', 'Highest', 'Critical')"
    elif metric == "todo":
        query += " AND metadata->>'statusCategory' = 'to do'"
    elif metric == "in_progress":
        query += " AND metadata->>'statusCategory' = 'in progress'"
    elif metric == "done":
        query += " AND metadata->>'statusCategory' = 'done'"
    elif metric == "stale":
        query += " AND metadata->>'statusCategory' = 'in progress' AND updated_at < NOW() - INTERVAL '3 days'"
        
    query += " LIMIT 50"
    res = await session.execute(text(query), params)
    return {"issues": [dict(r) for r in res.mappings().fetchall()]}

