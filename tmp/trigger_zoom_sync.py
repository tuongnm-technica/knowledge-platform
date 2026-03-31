import asyncio
import structlog
from datetime import datetime
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from apps.api.services.connectors_service import build_connector_for_instance
from ingestion.pipeline import IngestionPipeline

log = structlog.get_logger()

async def sync():
    async with AsyncSessionLocal() as session:
        # 1. Tìm Zoom instance
        res = await session.execute(text("SELECT id FROM connector_instances WHERE connector_type = 'zoom' LIMIT 1"))
        row = res.fetchone()
        if not row:
            print("Error: Zoom instance not found. Please configure it first.")
            return
        
        # FIX: Chuyển UUID sang string để tránh lỗi asyncpg DataError
        instance_id = str(row[0])
        print(f"Starting sync for Zoom instance: {instance_id}")

        # 2. Build connector
        # Note: we pass None for selection to sync all available
        connector = await build_connector_for_instance(session, "zoom", instance_id, None)
        
        # 3. Run Ingestion Pipeline
        pipeline = IngestionPipeline(session)
        
        print("Fetching and processing recordings... This may take a moment.")
        # Perform a full sync (incremental=False) for the first time to get history
        stats = await pipeline.run(connector, incremental=False, connector_key=f"zoom:{instance_id}")
        
        print("\nSync Completed!")
        print(f"-------------------")
        print(f"Fetched: {stats.get('fetched', 0)}")
        print(f"Indexed: {stats.get('indexed', 0)}")
        print(f"Skipped: {stats.get('skipped', 0)}")
        print(f"Errors:  {stats.get('errors', 0)}")
        
        await session.commit()

if __name__ == "__main__":
    asyncio.run(sync())
