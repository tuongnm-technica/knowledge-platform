
import asyncio
import json
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def inspect_worklogs():
    async with AsyncSessionLocal() as session:
        print("Checking Jira documents worklog sample:")
        query = text("""
            SELECT id, source_id, metadata->'worklog' 
            FROM documents 
            WHERE source = 'jira' AND metadata->'worklog' IS NOT NULL 
            LIMIT 5;
        """)
        res = await session.execute(query)
        rows = res.fetchall()
        if not rows:
            print("  No worklogs found in documents table!")
            # Check if any have empty worklog arrays
            query_total = text("SELECT COUNT(*) FROM documents WHERE source = 'jira';")
            total = (await session.execute(query_total)).scalar()
            print(f"  Total Jira documents: {total}")
        else:
            for row in rows:
                print(f"  ID: {row[0]}, Key: {row[1]}")
                print(f"  Worklog: {json.dumps(row[2], indent=2)[:500]}...")

        print("\nChecking Jira timetracking sample:")
        query_tt = text("""
            SELECT id, source_id, metadata->'timetracking'
            FROM documents 
            WHERE source = 'jira' AND metadata->'timetracking' IS NOT NULL 
            LIMIT 5;
        """)
        res_tt = await session.execute(query_tt)
        for row in res_tt.fetchall():
            print(f"  ID: {row[0]}, Key: {row[1]}, Timetracking: {row[2]}")

if __name__ == "__main__":
    asyncio.run(inspect_worklogs())
