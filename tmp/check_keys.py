
import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def check_key_consistency():
    async with AsyncSessionLocal() as session:
        print("--- PROJECT KEYS IN pm_metrics_daily ---")
        q1 = text("SELECT DISTINCT project_key FROM pm_metrics_daily")
        res1 = await session.execute(q1)
        print([r[0] for r in res1.fetchall()])
        
        print("\n--- PROJECT KEYS IN documents (Top 5) ---")
        q2 = text("SELECT DISTINCT metadata->>'project_key' as pk FROM documents WHERE source = 'jira' LIMIT 10")
        res2 = await session.execute(q2)
        print([r[0] for r in res2.fetchall()])

        print("\n--- SAMPLE DOCUMENT project_key FORMAT ---")
        q3 = text("SELECT metadata->>'project_key' FROM documents WHERE source = 'jira' AND metadata->>'project_key' IS NOT NULL LIMIT 1")
        res3 = await session.execute(q3)
        print(f"Sample: '{res3.scalar()}'")

if __name__ == "__main__":
    asyncio.run(check_key_consistency())
