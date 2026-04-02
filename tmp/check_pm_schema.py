
import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def check_pm_schema():
    async with AsyncSessionLocal() as session:
        for table in ["pm_metrics_daily", "pm_metrics_by_user", "pm_metrics_by_project"]:
            print(f"\nColumns in {table}:")
            query = text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
            res = await session.execute(query)
            for row in res.fetchall():
                print(f"  - {row[0]} ({row[1]})")

if __name__ == "__main__":
    asyncio.run(check_pm_schema())
