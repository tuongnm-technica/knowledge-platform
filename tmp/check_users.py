import asyncio
from sqlalchemy import select
from storage.db.db import UserORM, AsyncSessionLocal

async def list_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserORM))
        users = result.scalars().all()
        for u in users:
            print(f"Email: {u.email}, Name: {u.display_name}, Is Admin: {u.is_admin}, Role: {u.role}")

if __name__ == "__main__":
    asyncio.run(list_users())
