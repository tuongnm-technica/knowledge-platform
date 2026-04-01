import asyncio
import sys
import os
import uuid
from sqlalchemy import select, update

# Add current dir to path
sys.path.append(os.getcwd())

from storage.db.db import AsyncSessionLocal, LLMModelORM
from config.settings import settings

async def fix_ollama_urls():
    print(f"Targeting Base URL from settings: {settings.OLLAMA_BASE_URL}")
    
    async with AsyncSessionLocal() as session:
        # Update all ollama models that have localhost or incorrect base_url
        # We explicitly set them to settings.OLLAMA_BASE_URL
        stmt = (
            update(LLMModelORM)
            .where(LLMModelORM.provider == "ollama")
            .values(base_url=settings.OLLAMA_BASE_URL)
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        print(f"Update completed. Rows affected: {result.rowcount}")
        
        # Verify
        res = await session.execute(select(LLMModelORM).where(LLMModelORM.provider == "ollama"))
        models = res.scalars().all()
        for m in models:
            print(f"Model: {m.llm_model_name} | Base URL: {m.base_url}")

if __name__ == "__main__":
    asyncio.run(fix_ollama_urls())
