import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def check_sync_logs():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        # Check documents
        result = await conn.execute(text("SELECT count(*) FROM documents"))
        print(f"Total documents: {result.scalar()}")

        # Check graph tables
        result = await conn.execute(text("SELECT count(*) FROM entities"))
        print(f"Total entities: {result.scalar()}")

        result = await conn.execute(text("SELECT count(*) FROM entity_relations"))
        print(f"Total entity_relations: {result.scalar()}")

        result = await conn.execute(text("SELECT count(*) FROM document_links"))
        print(f"Total document_links: {result.scalar()}")

        # Check sync logs
        result = await conn.execute(text("SELECT count(*) FROM sync_logs"))
        print(f"Total sync logs: {result.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_sync_logs())
