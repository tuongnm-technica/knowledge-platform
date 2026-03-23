import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def run():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT count(*) FROM groups"))
        print(f"Groups count: {res.scalar()}")
        
        res = await conn.execute(text("SELECT count(*) FROM user_groups"))
        print(f"User-Group assignments: {res.scalar()}")
        
        res = await conn.execute(text("SELECT count(*) FROM users"))
        print(f"Users count: {res.scalar()}")
        
        print("\nGroups detail:")
        res = await conn.execute(text("SELECT id, name FROM groups"))
        for row in res.fetchall():
            print(f"- {row.id}: {row.name}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
