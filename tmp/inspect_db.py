
import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def inspect():
    async with AsyncSessionLocal() as session:
        print("Checking documents statusCategory:")
        res = await session.execute(text("SELECT metadata->>'statusCategory' as cat, COUNT(*) FROM documents WHERE source = 'jira' GROUP BY 1;"))
        for row in res.fetchall():
            print(f"  {row[0]}: {row[1]}")

        print("\nChecking documents project_key / project:")
        res = await session.execute(text("SELECT metadata->>'project_key' as pk, metadata->>'project' as p, COUNT(*) FROM documents WHERE source = 'jira' GROUP BY 1, 2;"))
        for row in res.fetchall():
            print(f"  pk: {row[0]}, p: {row[1]}, count: {row[2]}")

        print("\nChecking pm_metrics_daily:")
        res = await session.execute(text("SELECT * FROM pm_metrics_daily ORDER BY date DESC LIMIT 5;"))
        for row in res.fetchall():
            print(f"  {row}")

        print("\nChecking pm_metrics_by_project:")
        res = await session.execute(text("SELECT * FROM pm_metrics_by_project;"))
        for row in res.fetchall():
            print(f"  {row}")

        print("\nChecking doc_drafts (risks/retro):")
        res = await session.execute(text("SELECT doc_type, COUNT(*) FROM doc_drafts GROUP BY 1;"))
        for row in res.fetchall():
            print(f"  {row[0]}: {row[1]}")

if __name__ == "__main__":
    asyncio.run(inspect())
