import asyncio
from storage.db.db import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        print("Checking AFW statuses...")
        res = await conn.execute(text("SELECT metadata->>'statusCategory' as sc, metadata->>'status' as s, COUNT(*) FROM documents WHERE source='jira' AND (metadata->>'project_key' ILIKE 'AFW' OR metadata->>'project' ILIKE 'AFW') GROUP BY 1, 2"))
        print(f"Stats: {res.fetchall()}")
        
        print("\nChecking AFW worklog data...")
        res = await conn.execute(text("SELECT metadata->'worklog' FROM documents WHERE source='jira' AND (metadata->>'project_key' ILIKE 'AFW' OR metadata->>'project' ILIKE 'AFW') AND (metadata->'worklog' IS NOT NULL AND jsonb_array_length(metadata->'worklog') > 0) LIMIT 1"))
        worklog = res.fetchone()
        if worklog:
            print(f"Worklog Sample: {worklog[0]}")
        else:
            print("No detailed worklogs found in metadata list.")

if __name__ == "__main__":
    asyncio.run(check())
