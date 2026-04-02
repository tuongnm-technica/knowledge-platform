from datetime import datetime, timedelta
from sqlalchemy import text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models.document import SourceType
from storage.db.db import (
    PMMetricsDailyORM, 
    PMMetricsByUserORM, 
    PMMetricsByProjectORM,
    DocumentORM
)
import structlog
import json

log = structlog.get_logger()

async def aggregate_pm_metrics(session: AsyncSession, project_key: str):
    """
    Performs pre-aggregation of PM metrics for a specific project.
    Now with Sprint scoping and Median calculation.
    """
    log.info("pm_metrics.aggregation.start", project=project_key)
    
    # 1. Fetch Issues with Sprint and Epic metadata
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = text("""
        SELECT 
            CAST(metadata AS JSONB)->>'statusCategory' as cat, 
            CAST(metadata AS JSONB)->>'priority' as priority, 
            CAST(metadata AS JSONB)->'assignee'->>'accountId' as account_id, 
            CAST(metadata AS JSONB)->'assignee'->>'displayName' as display_name, 
            CAST(metadata AS JSONB)->>'sprint' as sprint_json, 
            CAST(metadata AS JSONB)->>'epic' as epic_json, 
            updated_at, 
            created_at, 
            CAST(metadata AS JSONB)->>'resolved_date' as resolved_date 
        FROM documents 
        WHERE source = 'jira' 
          AND (
              metadata->>'project_key' ILIKE '%' || CAST(:p AS TEXT) || '%' 
              OR metadata->>'project' ILIKE '%' || CAST(:p AS TEXT) || '%' 
              OR CAST(:p AS TEXT) ILIKE '%' || (metadata->>'project_key') || '%'
          )
    """)
    res = await session.execute(query, {"p": project_key})
    issues = res.mappings().fetchall()
    
    if not issues:
        log.warning("pm_metrics.aggregation.no_data", project=project_key)
        return

    # 2. Identify Active Sprint
    active_sprint_id = None
    for i in issues:
        sj = i['sprint_json']
        if sj:
            try:
                s_obj = json.loads(sj) if isinstance(sj, str) else sj
                if s_obj.get('state') == 'ACTIVE':
                    active_sprint_id = s_obj.get('id')
                    break
            except: pass

    # Scope Issues to Active Sprint if found, otherwise keep all
    sprint_issues = issues
    if active_sprint_id:
        def issue_in_sprint(i):
            sj = i['sprint_json']
            if not sj: return False
            s_str = str(sj)
            return f"id={active_sprint_id}," in s_str or f"id={active_sprint_id}]" in s_str or f"\"id\":{active_sprint_id}" in s_str or f"\"id\": \"{active_sprint_id}\"" in s_str

        sprint_issues = [i for i in issues if issue_in_sprint(i)]

    todo = [i for i in sprint_issues if str(i['cat']).lower() in ('to do', 'open', 'new', 'todo')]
    wip = [i for i in sprint_issues if str(i['cat']).lower() in ('in progress', 'doing', 'wip', 'indeterminate')]
    done = [i for i in sprint_issues if str(i['cat']).lower() in ('done', 'resolved', 'closed', 'completed')]
    high_pri = [i for i in sprint_issues if str(i['priority']).lower() in ('high', 'highest', 'critical', 'urgent')]
    
    # Calculate MEDIAN Lead Time
    lead_times = []
    for d in done:
        c_at = d['created_at']
        r_str = d['resolved_date']
        if r_str:
            try:
                r_at = datetime.fromisoformat(r_str)
                diff = (r_at - c_at).total_seconds() / 86400.0
                if diff >= 0: lead_times.append(diff)
            except: pass
            
    lead_times.sort()
    mid = len(lead_times) // 2
    median_lt = 0.0
    if len(lead_times) > 0:
        median_lt = lead_times[mid] if len(lead_times) % 2 != 0 else (lead_times[mid-1] + lead_times[mid]) / 2

    # Update Daily Metrics (Scoped to current day, potentially scoped to sprint too)
    daily = PMMetricsDailyORM(
        id=None,
        date=today,
        project_key=project_key,
        todo_count=len(todo),
        in_progress_count=len(wip),
        done_count=len(done),
        high_priority_count=len(high_pri),
        avg_lead_time_days=float(median_lt)
    )
    await session.execute(text("DELETE FROM pm_metrics_daily WHERE date = :d AND project_key = :p"), {"d": today, "p": project_key})
    session.add(daily)

    # 3. Per-User Metrics
    user_map = {}
    stale_threshold = now - timedelta(days=3)
    for i in sprint_issues:
        uid = i['account_id'] or i['display_name'] or "Unassigned"
        uname = i['display_name'] or "Unassigned"
        if uid not in user_map:
            user_map[uid] = {"name": uname, "todo": 0, "wip": 0, "done": 0, "stale": 0}
        
        cat = i['cat']
        if cat == 'to do': user_map[uid]["todo"] += 1
        elif cat == 'in progress': 
            user_map[uid]["wip"] += 1
            if i['updated_at'] < stale_threshold:
                user_map[uid]["stale"] += 1
        elif cat == 'done': user_map[uid]["done"] += 1

    await session.execute(text("DELETE FROM pm_metrics_by_user WHERE project_key = :p"), {"p": project_key})
    for uid, s in user_map.items():
        session.add(PMMetricsByUserORM(
            user_id=uid, display_name=s["name"], project_key=project_key,
            todo_count=s["todo"], in_progress_count=s["wip"], done_count=s["done"], stale_count=s["stale"]
        ))

    # 4. Project Level (Velocity & Bottlenecks)
    last_week = now - timedelta(days=7)
    v_now = len([d for d in done if d['updated_at'] > last_week])
    
    # Bottleneck detection
    insight = None
    if len(wip) > max(5, v_now * 2):
        insight = "⚠️ Bottleneck detected: WIP is significantly higher than weekly throughput (Velocity)."
    
    risk = (len(high_pri) * 3) + (sum(u["stale"] for u in user_map.values()) * 5)
    risk = min(100, risk)
    status = "healthy"
    if risk > 60: status = "critical"
    elif risk > 30: status = "warning"
    
    await session.execute(text("DELETE FROM pm_metrics_by_project WHERE project_key = :p"), {"p": project_key})
    session.add(PMMetricsByProjectORM(
        project_key=project_key,
        velocity_weekly=float(v_now),
        velocity_delta_pct=0.0, # compare logic simplified for demo
        risk_score=float(risk),
        health_status=status,
        insight=insight
    ))
    await session.commit()
    log.info("pm_metrics.aggregation.done", project=project_key, risk=risk, status=status)
