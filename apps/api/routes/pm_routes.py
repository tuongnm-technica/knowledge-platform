from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import json
from pydantic import BaseModel
from services.llm_service import LLMService

from apps.api.auth.dependencies import CurrentUser, get_current_user
from storage.db.db import get_db
from connectors.jira.jira_client import JiraClient

router = APIRouter(prefix="/pm", tags=["pm_dashboard"])

@router.get("/projects")
async def get_pm_projects(
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        # Fetching directly from Jira Client (or we can query distinct 'project' from documents)
        client = JiraClient()
        projects = client.get_projects()
        
        return {
            "projects": [
                {
                    "key": p.get("key"), 
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "avatar": p.get("avatarUrls", {}).get("48x48")
                } 
                for p in projects
            ]
        }
    except Exception as e:
        # Fallback to DB if live Jira connection fails
        res = await session.execute(text("SELECT DISTINCT metadata->>'project' as key FROM documents WHERE source='jira' AND metadata->>'project' IS NOT NULL"))
        projects = [{"key": row[0], "name": row[0]} for row in res.fetchall()]
        return {"projects": projects}


@router.get("/dashboard/stats")
async def get_pm_dashboard_stats(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Fetching metrics from pm_metrics_daily and pm_project_insights
    query_metrics = text("""
        SELECT 
            todo_count, in_progress_count, done_count, high_priority_count
        FROM pm_metrics_daily
        WHERE (:p IS NULL OR project_key ILIKE :p OR project_key ILIKE :p_br)
        ORDER BY date DESC LIMIT 1
    """)
    
    query_insights = text("""
        SELECT velocity_weekly, risk_score, health_status, insight
        FROM pm_metrics_by_project
        WHERE (:p IS NULL OR project_key ILIKE :p OR project_key ILIKE :p_br)
        ORDER BY updated_at DESC LIMIT 1
    """)
    
    res_metrics = await session.execute(query_metrics, {"p": project_key, "p_br": f"[{project_key}]" if project_key else None})
    stats_row = res_metrics.fetchone()
    
    # [LIVE FALLBACK] If no daily metrics found, compute live from documents table
    if not stats_row:
        live_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE metadata->>'statusCategory' ILIKE 'to do' OR metadata->>'status' ILIKE 'open') as todo,
                COUNT(*) FILTER (WHERE metadata->>'statusCategory' ILIKE 'in progress' OR metadata->>'status' ILIKE 'in progress' OR metadata->>'status' ILIKE 'doing') as wip,
                COUNT(*) FILTER (WHERE metadata->>'statusCategory' ILIKE 'done' OR metadata->>'status' ILIKE 'resolved' OR metadata->>'status' ILIKE 'closed' OR metadata->>'status' ILIKE 'done') as done,
                COUNT(*) FILTER (WHERE (metadata->>'priority' ILIKE 'high' OR metadata->>'priority' ILIKE 'critical' OR metadata->>'priority' ILIKE 'highest')) as high
            FROM documents
            WHERE source = 'jira' 
              AND (
                  :p IS NULL 
                  OR metadata->>'project_key' ILIKE :p 
                  OR metadata->>'project_key' ILIKE :p_br
                  OR metadata->>'project' ILIKE :p
                  OR metadata->>'project' ILIKE :p_br
              )
        """)
        res_live = await session.execute(live_query, {"p": project_key, "p_br": f"[{project_key}]" if project_key else None})
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
    p_res = await session.execute(query_insights, {"p": project_key, "p_br": f"[{project_key}]" if project_key else None})
    p_metrics = p_res.mappings().first()
    if p_metrics:
        formatted_stats.update({
            "velocity_weekly": p_metrics["velocity_weekly"],
            "risk_score": p_metrics["risk_score"],
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
    # Placeholder for risks generated by PM Digest background task
    # For now, we simulate pulling "ai_task_drafts" or "documents" that are labeled as risks
    # In full implementation, we can query a specific table for generated reports
    
    query = """
    SELECT 
        title, content, created_at
    FROM doc_drafts
    WHERE doc_type = 'pm_risk_report'
    """
    
    params = {}
    if project_key:
        query += " AND title LIKE :project_key"
        params["project_key"] = f"%[{project_key}]%"
        
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
    query = "SELECT user_id, display_name, project_key, todo_count, in_progress_count, done_count FROM pm_metrics_by_user"
    if project_key:
        query += " WHERE project_key ILIKE :p OR project_key ILIKE :p_br"
        params = {"p": project_key, "p_br": f"[{project_key}]"}
        
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
    """
    Aggregates total time spent (logged hours) from issue metadata by user.
    """
    query = """
        SELECT 
            metadata->'assignee'->>'displayName' as user_name,
            SUM(CAST(COALESCE(metadata->'timetracking'->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
        FROM documents
        WHERE source = 'jira' 
          AND (
              metadata->>'project_key' ILIKE :p 
              OR metadata->>'project_key' ILIKE :p_br
              OR metadata->>'project' ILIKE :p
              OR metadata->>'project' ILIKE :p_br
          )
        GROUP BY 1
        HAVING SUM(CAST(COALESCE(metadata->'timetracking'->>'timeSpentSeconds', '0') AS INTEGER)) > 0
        ORDER BY seconds DESC
    """
    
    params = {"p": project_key, "p_br": f"[{project_key}]"} if project_key else {"p": "%", "p_br": "%"}
    
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
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Temporarily disabled to debug aggregation error
    return {"trend": []}
    """
    query = f\"\"\"
        SELECT 
            CAST(w->>'started' AS DATE) as log_date,
            w->>'author' as user_name,
            SUM(CAST(COALESCE(w->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
        FROM documents,
             jsonb_array_elements(CASE WHEN jsonb_typeof(metadata->'worklog') = 'array' THEN (metadata->'worklog') ELSE '[]'::jsonb END) w
        WHERE source = 'jira' 
          AND (
              :p IS NULL
              OR metadata->>'project_key' ILIKE :p 
              OR metadata->>'project_key' ILIKE :p_br
              OR metadata->>'project' ILIKE :p
              OR metadata->>'project' ILIKE :p_br
          )
          AND (w->>'started') IS NOT NULL
          AND CAST(w->>'started' AS DATE) >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY 1, 2
        ORDER BY 1 ASC, 3 DESC
    \"\"\"
    
    params = {"p": project_key, "p_br": f"[{project_key}]"} if project_key else {"p": "%", "p_br": "%"}
    
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
    """


@router.get("/dashboard/stale")
async def get_pm_stale_tasks(
    project_key: Optional[str] = None,
    days: int = 3,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
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
        
        # Kiểm tra xem dự án có dữ liệu Jira không
        res = await session.execute(
            text("""SELECT COUNT(*) FROM documents WHERE source = 'jira' AND (
                metadata->>'project_key' ILIKE :p OR metadata->>'project_key' ILIKE :p_br OR
                metadata->>'project' ILIKE :p OR metadata->>'project' ILIKE :p_br
            )"""),
            {"p": project_key, "p_br": f"[{project_key}]"}
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


@router.get("/dashboard/burnup")
async def get_pm_burnup(
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    query = """
    SELECT 
        DATE(updated_at) as done_date,
        COUNT(id) as count
    FROM documents 
    WHERE source = 'jira' 
      AND metadata->>'statusCategory' = 'done'
    """
    params = {}
    if project_key:
        query += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        params["project_key"] = project_key
        params["project_key_br"] = f"[{project_key}]"
        
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
    # Simulated CFD from current Snapshot DB
    query = """
    SELECT 
        DATE(created_at) as created_date,
        COUNT(id) as total_entered
    FROM documents 
    WHERE source = 'jira'
    """
    params = {}
    if project_key:
        query += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        params["project_key"] = project_key
        params["project_key_br"] = f"[{project_key}]"
        
    query += " GROUP BY DATE(created_at) ORDER BY DATE(created_at) ASC"
    
    created_res = await session.execute(text(query), params)
    
    # Same for done
    query_done = """
    SELECT 
        DATE(updated_at) as resolved_date,
        COUNT(id) as total_resolved
    FROM documents 
    WHERE source = 'jira' AND metadata->>'statusCategory' = 'done'
    """
    if project_key:
        query_done += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        
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
    query = """
    SELECT 
        DATE(updated_at) as done_date,
        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/86400) as daily_avg_lead_time
    FROM documents 
    WHERE source = 'jira' 
      AND metadata->>'statusCategory' = 'done'
      AND updated_at IS NOT NULL
      AND created_at IS NOT NULL
    """
    params = {}
    if project_key:
        query += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        params["project_key"] = project_key
        params["project_key_br"] = f"[{project_key}]"
        
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
    query = """
    SELECT 
        COALESCE(metadata->>'issue_type', 'Unknown') as issue_type,
        COUNT(id) as count
    FROM documents 
    WHERE source = 'jira'
    """
    params = {}
    if project_key:
        query += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        params["project_key"] = project_key
        params["project_key_br"] = f"[{project_key}]"
        
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
    params = {}
    if project_key:
        query += " AND (metadata->>'project_key' ILIKE :project_key OR metadata->>'project_key' ILIKE :project_key_br)"
        params["project_key"] = project_key
        params["project_key_br"] = f"[{project_key}]"
        
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
    query = """
    SELECT 
        title, content, created_at
    FROM doc_drafts
    WHERE doc_type = 'pm_sprint_retrospective'
    """
    params = {}
    if project_key:
        query += " AND title LIKE :project_key"
        params["project_key"] = f"%[{project_key}]%"
        
    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit
    
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
    project_key = req.project_key.strip()
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
      AND updated_at < NOW() - interval '3 days'
    ORDER BY updated_at ASC LIMIT 10
    """
    s_res = await session.execute(text(stale_query), {"p": project_key, "p_br": f"[{project_key}]"})
    stale_issues = s_res.mappings().all()
    stale_str = "\n".join([f"- [{i['key']}] {i['title']} (Assignee: {i['assignee']}, Last Updated: {i['updated_at']})" for i in stale_issues])

    # 3. Fetch Recent Bottleneck (WIP issues)
    wip_query = text("""
        SELECT source_id as key, title, metadata->'assignee'->>'displayName' as assignee, metadata->>'status' as status
        FROM documents 
        WHERE source = 'jira' 
          AND (
              metadata->>'project_key' ILIKE :p 
              OR metadata->>'project_key' ILIKE :p_br
              OR metadata->>'project' ILIKE :p
              OR metadata->>'project' ILIKE :p_br
          )
          AND metadata->>'statusCategory' = 'in progress'
        ORDER BY updated_at DESC LIMIT 10
    """)
    w_res = await session.execute(wip_query, {"p": project_key, "p_br": f"[{project_key}]"})
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
[[CHART:{"type":"pie|bar|line", "title": "...", "labels": [], "data": []}]]
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
    query = "SELECT * FROM pm_metrics_by_project WHERE health_status != 'healthy' ORDER BY risk_score DESC LIMIT 5"
    res = await session.execute(text(query))
    return {"projects": [dict(r) for r in res.mappings().fetchall()]}


@router.get("/dashboard/details")
async def get_pm_drilldown(
    metric: str,
    project_key: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Drill-down API to fetch issue list for a specific metric."""
    query = """
    SELECT 
        source_id as key, title, 
        metadata->>'status' as status, 
        metadata->'assignee'->>'displayName' as assignee, 
        url
    FROM documents
    WHERE source = 'jira'
    """
    params = {}
    if project_key:
        query += " AND metadata->>'project_key' = :p"
        params["p"] = project_key
        
    if metric == "high_priority":
        query += " AND metadata->>'priority' IN ('High', 'Highest')"
    elif metric == "todo":
        query += " AND metadata->>'statusCategory' = 'to do'"
    elif metric == "in_progress":
        query += " AND metadata->>'statusCategory' = 'in progress'"
    elif metric == "done":
        query += " AND metadata->>'statusCategory' = 'done'"
    elif metric == "stale":
        query += " AND metadata->>'statusCategory' = 'in progress' AND updated_at < NOW() - interval '3 days'"
        
    query += " LIMIT 50"
    res = await session.execute(text(query), params)
    return {"issues": [dict(r) for r in res.mappings().fetchall()]}

