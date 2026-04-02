
import asyncio
import json
from datetime import datetime
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def debug_dashboard_data():
    async with AsyncSessionLocal() as session:
        print("--- DEBUGGING DASHBOARD DATA ---")
        
        # 1. Check pm_metrics_daily
        print("\n1. Contents of pm_metrics_daily (Last 5 rows):")
        query_daily = text("SELECT date, project_key, todo_count, in_progress_count, done_count, high_priority_count FROM pm_metrics_daily ORDER BY date DESC, project_key LIMIT 10")
        res_daily = await session.execute(query_daily)
        rows = res_daily.fetchall()
        for r in rows:
            print(f"   Date: {r[0]}, Project: {r[1]}, Todo: {r[2]}, WIP: {r[3]}, Done: {r[4]}, High: {r[5]}")
            
        # 2. Check the "Global View" query logic specifically
        print("\n2. Executing Global View SUM query (same as pm_routes.py):")
        query_global = text("""
            SELECT 
                SUM(todo_count) as todo, 
                SUM(in_progress_count) as wip, 
                SUM(done_count) as done, 
                SUM(high_priority_count) as high
            FROM pm_metrics_daily
            WHERE date = (SELECT MAX(date) FROM pm_metrics_daily)
        """)
        res_global = await session.execute(query_global)
        row_global = res_global.fetchone()
        print(f"   Result: {row_global}")
        
        # 3. Check Live Data for sanity check
        print("\n3. Executing Live Query (Global View):")
        live_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'to do' OR (metadata)::jsonb->>'status' ILIKE 'open') as todo,
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'in progress' OR (metadata)::jsonb->>'status' ILIKE 'in progress' OR (metadata)::jsonb->>'status' ILIKE 'doing') as wip,
                COUNT(*) FILTER (WHERE (metadata)::jsonb->>'statusCategory' ILIKE 'done' OR (metadata)::jsonb->>'status' ILIKE 'resolved' OR (metadata)::jsonb->>'status' ILIKE 'closed' OR (metadata)::jsonb->>'status' ILIKE 'done') as done,
                COUNT(*) FILTER (WHERE ((metadata)::jsonb->>'priority' ILIKE 'high' OR (metadata)::jsonb->>'priority' ILIKE 'critical' OR (metadata)::jsonb->>'priority' ILIKE 'highest')) as high
            FROM documents
            WHERE source = 'jira'
        """)
        res_live = await session.execute(live_query)
        row_live = res_live.fetchone()
        print(f"   Live Result: {row_live}")

        # 4. Check Log-time Trend data for 250 days
        print("\n4. Checking Log-time Trend for 250 days:")
        query_trend = text("""
            SELECT 
                CAST(w->>'started' AS DATE) as log_date,
                w->>'author' as user_name,
                SUM(CAST(COALESCE(w->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
            FROM documents,
                 jsonb_array_elements(CASE WHEN jsonb_typeof((metadata->'worklog')::jsonb) = 'array' THEN (metadata->'worklog')::jsonb ELSE '[]'::jsonb END) w
            WHERE source = 'jira' 
              AND (w->>'started') IS NOT NULL
              AND CAST(w->>'started' AS DATE) >= CURRENT_DATE - INTERVAL '250 days'
            GROUP BY 1, 2
            ORDER BY 1 DESC LIMIT 5
        """)
        res_trend = await session.execute(query_trend)
        rows_trend = res_trend.fetchall()
        print(f"   Trend Rows (Latest 5): {rows_trend}")

if __name__ == "__main__":
    asyncio.run(debug_dashboard_data())
