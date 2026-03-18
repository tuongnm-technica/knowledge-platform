import asyncio
import os
import sys

# Ensure the root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.db.db import engine, Base

async def run_migration():
    async with engine.begin() as conn:
        print("Running schema migration (create_all) to add ProjectMemoryORM...")
        await conn.run_sync(Base.metadata.create_all)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(run_migration())
