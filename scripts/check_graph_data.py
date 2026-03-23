import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def run():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        # Check entities for recent docs (last 30 days)
        since = datetime.now() - timedelta(days=30)
        result = await conn.execute(text("""
            SELECT count(DISTINCT document_id) 
            FROM document_entities de
            JOIN documents d ON d.id = de.document_id
            WHERE d.updated_at >= :since
        """), {"since": since})
        print(f"Recent documents with entities: {result.scalar()}")

        result = await conn.execute(text("""
            SELECT count(*) 
            FROM document_entities de
            JOIN documents d ON d.id = de.document_id
            WHERE d.updated_at >= :since
        """), {"since": since})
        print(f"Total entity associations for recent docs: {result.scalar()}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
