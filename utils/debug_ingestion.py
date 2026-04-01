import asyncio
import json
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def debug():
    async with AsyncSessionLocal() as session:
        print("--- 1. LAST 5 SYNC LOGS ---")
        res = await session.execute(text("SELECT connector, status, errors, started_at, finished_at FROM sync_logs ORDER BY started_at DESC LIMIT 5"))
        for row in res.mappings().all():
            print(f"Connector: {row['connector']}, Status: {row['status']}, Errors: {row['errors']}, Started: {row['started_at']}")

        print("\n--- 2. JIRA METADATA SAMPLE ---")
        res = await session.execute(text("SELECT metadata FROM documents WHERE source = 'jira' LIMIT 3"))
        for row in res.mappings().all():
            print(json.dumps(row['metadata'], indent=2))

        print("\n--- 3. JIRA PROJECT KEYS IN DB ---")
        res = await session.execute(text("SELECT DISTINCT metadata->>'project' as pkey FROM documents WHERE source = 'jira'"))
        for row in res.mappings().all():
            print(f"Project Key: {row['pkey']}")

if __name__ == "__main__":
    asyncio.run(debug())
