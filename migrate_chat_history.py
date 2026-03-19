import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.db.db import engine, Base
import models.chat  # Import để SQLAlchemy nhận diện được bảng

async def run_migration():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(run_migration())