import asyncio
from storage.db.db import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        print("Checking project_key...")
        res = await conn.execute(text("SELECT DISTINCT metadata->>'project_key' FROM documents WHERE source='jira'"))
        rows = res.fetchall()
        print(f"Project Keys: {rows}")
        
        print("Checking pm_metrics_daily...")
        res = await conn.execute(text("SELECT COUNT(*) FROM pm_metrics_daily"))
        print(f"Daily Metrics Count: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
