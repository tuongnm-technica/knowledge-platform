import asyncio
from storage.db.db import AsyncSessionLocal, UserORM
from sqlalchemy import select

async def check_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserORM))
        users = result.scalars().all()
        if not users:
            print("No users found.")
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Is Admin: {user.is_admin}")

if __name__ == "__main__":
    asyncio.run(check_users())
