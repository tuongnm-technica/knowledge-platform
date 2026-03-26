
import asyncio
import bcrypt
from sqlalchemy import update
from storage.db.db import UserORM, AsyncSessionLocal

async def reset_password(email: str, new_password: str):
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(UserORM)
            .where(UserORM.email == email)
            .values(password_hash=hashed)
        )
        await session.commit()
        print(f"Password for {email} has been reset to {new_password}")

if __name__ == "__main__":
    asyncio.run(reset_password("admin@technica.ai", "Abcd@1234!"))
