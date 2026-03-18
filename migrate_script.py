import asyncio
import json
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def alter_table():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("ALTER TABLE doc_drafts ADD COLUMN IF NOT EXISTS structured_data JSON DEFAULT '{}'::json"))
            await session.commit()
            print('Done migrating DB')
    except Exception as e:
        print('Error:', e)

asyncio.run(alter_table())
