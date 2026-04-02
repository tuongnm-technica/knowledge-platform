
import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def verify_final():
    async with AsyncSessionLocal() as session:
        print("Checking Dashboard Stats (Global):")
        # Simulate logic from pm_routes.py
        query = text("SELECT SUM(todo_count), SUM(in_progress_count), SUM(done_count), SUM(high_priority_count) FROM pm_metrics_daily")
        res = await session.execute(query)
        stats = res.fetchone()
        print(f"  Stats: {stats}")
        
        print("\nChecking Log-time Trend (Global):")
        # Simulate logic from pm_routes.py
        query_trend = text("""
            SELECT 
                CAST(w->>'started' AS DATE) as log_date,
                w->>'author' as user_name,
                SUM(CAST(COALESCE(w->>'timeSpentSeconds', '0') AS INTEGER)) as seconds
            FROM documents,
                 jsonb_array_elements(CASE WHEN jsonb_typeof((metadata->'worklog')::jsonb) = 'array' THEN (metadata->'worklog')::jsonb ELSE '[]'::jsonb END) w
            WHERE source = 'jira' 
              AND (w->>'started') IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1 ASC LIMIT 5
        """)
        res_trend = await session.execute(query_trend)
        rows = res_trend.fetchall()
        for r in rows:
            print(f"  Trend: {r}")

if __name__ == "__main__":
    asyncio.run(verify_final())
