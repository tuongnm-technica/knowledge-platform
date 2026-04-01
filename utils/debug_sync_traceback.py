import asyncio
import traceback
from apps.api.services.connectors_service import _run_sync_task

async def test_sync():
    print("--- TESTING JIRA SYNC ---")
    try:
        # Assuming 'Default' exists for JIRA
        # Check current instances first to be sure
        from sqlalchemy import text
        from storage.db.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT id FROM connector_instances WHERE connector_type='jira' LIMIT 1"))
            row = res.fetchone()
            if not row:
                print("No JIRA instance found.")
                return
            instance_id = row[0]
            print(f"JIRA Instance ID: {instance_id}")

        await _run_sync_task("jira", str(instance_id), incremental=False)
        print("Sync completed successfully.")
    except Exception as e:
        print("Sync FAILED with exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sync())
