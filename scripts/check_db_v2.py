import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def check_db():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("--- DOCUMENTS COLUMN NAMES ---")
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'documents'"))
        for row in result.fetchall():
            print(row[0])
            
        print("\n--- RECENT SYNC LOGS ---")
        result = await conn.execute(text("SELECT id, connector, status, started_at, finished_at, fetched, indexed, errors FROM sync_logs ORDER BY started_at DESC LIMIT 20"))
        for row in result.fetchall():
            print(row)
            
        print("\n--- DOCUMENT COUNT BY SOURCE ---")
        result = await conn.execute(text("SELECT source, COUNT(*) FROM documents GROUP BY source"))
        for row in result.fetchall():
            print(row)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_db())
