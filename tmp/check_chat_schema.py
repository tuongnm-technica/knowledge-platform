import asyncio
from sqlalchemy import text
from storage.db.db import engine

async def check_schema():
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'chat_messages'
        """))
        cols = [row[0] for row in result.all()]
        print(f"COLUMNS: {cols}")

if __name__ == "__main__":
    asyncio.run(check_schema())
