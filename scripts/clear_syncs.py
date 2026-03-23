import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def clear_syncs():
    async with AsyncSessionLocal() as session:
        print("Clearing 'running' sync logs...")
        await session.execute(text("UPDATE sync_logs SET status = 'failed', finished_at = NOW() WHERE status = 'running'"))
        await session.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(clear_syncs())
