import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as session:
        # PostgreSQL specific query to list columns
        res = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'documents'
        """))
        cols = res.fetchall()
        print("Columns in 'documents' table:")
        for col in cols:
            print(f" - {col[0]}: {col[1]}")

if __name__ == "__main__":
    asyncio.run(check())
