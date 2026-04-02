
import asyncio
import json
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def inspect_worklogs_dates():
    async with AsyncSessionLocal() as session:
        print("Checking Jira worklog dates:")
        query = text("""
            SELECT 
                w->>'started' as started,
                w->>'author' as author,
                w->>'timeSpentSeconds' as seconds
            FROM documents,
                 jsonb_array_elements(CASE WHEN jsonb_typeof(metadata->'worklog') = 'array' THEN metadata->'worklog' ELSE '[]'::jsonb END) w
            WHERE source = 'jira'
            LIMIT 10;
        """)
        res = await session.execute(query)
        rows = res.fetchall()
        if not rows:
            print("  No worklog entries found!")
        else:
            for row in rows:
                print(f"  Started: {row[0]}, Author: {row[1]}, Seconds: {row[2]}")

if __name__ == "__main__":
    asyncio.run(inspect_worklogs_dates())
