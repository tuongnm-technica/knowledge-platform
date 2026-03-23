import asyncio
import uuid
import sys
from storage.db.db import AsyncSessionLocal
from sqlalchemy import text
from orchestration.agent_tasks import run_agent_job

async def main():
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    
    # 1. Provide a dummy user ID by getting the first user in DB
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id FROM users LIMIT 1"))
        user_id_row = res.mappings().first()
        if not user_id_row:
            print("No users found in database.")
            return
        user_id = user_id_row["id"]
        
        # 1.5 Add dummy session
        await session.execute(
            text("""
            INSERT INTO chat_sessions (id, user_id, title) 
            VALUES (:id, :u, 'Dummy Session')
            """),
            {"id": session_id, "u": user_id}
        )
        
        # 2. Add dummy job record
        await session.execute(
            text("""
            INSERT INTO chat_jobs (id, user_id, session_id, question, status) 
            VALUES (:id, :u, :s, 'Hello, what is AI?', 'running')
            """),
            {"id": job_id, "u": user_id, "s": session_id}
        )
        await session.commit()
        
    print(f"Triggering job {job_id} for user {user_id}")
    await run_agent_job({}, job_id, user_id, "Hello, what is AI?", session_id)
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
