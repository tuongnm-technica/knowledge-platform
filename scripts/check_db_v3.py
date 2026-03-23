import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import json

DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def check_db():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        print("--- TABLES ---")
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        for row in result.fetchall():
            print(f"Table: {row[0]}")
            
        print("\n--- DOCUMENTS COLUMNS ---")
        result = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'documents'"))
        for row in result.fetchall():
            print(f"Col: {row[0]} ({row[1]})")
            
        print("\n--- SYNC LOGS (Last 5) ---")
        result = await conn.execute(text("SELECT id, connector, status, started_at, finished_at, fetched, indexed, errors FROM sync_logs ORDER BY started_at DESC LIMIT 5"))
        for row in result.fetchall():
            print(row)
            
        print("\n--- AI TASK DRAFTS (Last 5) ---")
        result = await conn.execute(text("SELECT id, title, status, source_type, created_at FROM ai_task_drafts ORDER BY created_at DESC LIMIT 5"))
        for row in result.fetchall():
            print(row)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_db())
