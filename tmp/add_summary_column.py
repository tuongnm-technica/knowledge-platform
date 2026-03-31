import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def migrate():
    async with AsyncSessionLocal() as session:
        print("Adding 'summary' column to 'documents' table...")
        try:
            await session.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT"))
            await session.commit()
            print("Successfully added 'summary' column.")
        except Exception as e:
            print(f"Error adding column: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(migrate())
