
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_session_maker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.getcwd())

from config.settings import settings
from orchestration.agent import Agent

async def debug_ask():
    # Setup DB
    from storage.db.db import engine
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    user_id = "tuongnm" # The user from logs
    question = "xin chào"
    
    print(f"Testing Agent.ask with question: {question}")
    async with async_session() as session:
        agent = Agent(session, user_id)
        try:
            result = await agent.ask(question)
            print("Response success!")
            print(result.get("answer"))
        except Exception as e:
            import traceback
            print("Caught exception!")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_ask())
