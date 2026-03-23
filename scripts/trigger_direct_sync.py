import asyncio
import structlog
from apps.api.services.connectors_service import start_connector_sync
from storage.db.db import AsyncSessionLocal
from fastapi import BackgroundTasks

async def trigger_direct():
    structlog.configure() # Basic config for logs
    instance_id = "df94a2d8-ff0a-42ae-b2a8-cbd3452ab9c7"
    connector_type = "confluence"
    
    bg_tasks = BackgroundTasks()
    async with AsyncSessionLocal() as session:
        print(f"Triggering sync for {connector_type}:{instance_id}...")
        res = await start_connector_sync(session, bg_tasks, connector_type, instance_id, incremental=False)
        print(f"Result: {res}")
        
    # If it added to bg_tasks (it shouldn't if Redis is working, it should enqueue to Redis)
    # but let's wait a bit to see logs
    await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(trigger_direct())
