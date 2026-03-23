import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def count_docs():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT COUNT(*) FROM documents"))
        print(f"Total documents: {res.scalar()}")
        res = await session.execute(text("SELECT id, connector, status, fetched, indexed, errors FROM sync_logs ORDER BY id DESC LIMIT 1"))
        print(f"Latest sync log: {res.fetchone()}")

if __name__ == "__main__":
    asyncio.run(count_docs())
