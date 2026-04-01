import asyncio
import uuid
from storage.db.db import AsyncSessionLocal, UserORM
from sqlalchemy import select, text
import bcrypt

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

async def create_admin():
    email = "admin@technica.ai"
    password = "Admin123!"
    display_name = "System Administrator"
    
    async with AsyncSessionLocal() as session:
        # Check if user exists
        result = await session.execute(select(UserORM).where(UserORM.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User {email} already exists. Updating password...")
            user.password_hash = _hash_password(password)
            user.is_admin = True
            user.role = "system_admin"
        else:
            print(f"Creating new admin user: {email}")
            user_id = f"user_admin_{uuid.uuid4().hex[:6]}"
            new_user = UserORM(
                id=user_id,
                email=email,
                display_name=display_name,
                password_hash=_hash_password(password),
                is_active=True,
                is_admin=True,
                role="system_admin"
            )
            session.add(new_user)
        
        await session.commit()
        print(f"✅ Admin user {email} is ready. Password: {password}")

if __name__ == "__main__":
    asyncio.run(create_admin())
