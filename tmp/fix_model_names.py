import asyncio
import uuid
import sys
import os

sys.path.append(os.getcwd())

from storage.db.db import AsyncSessionLocal, LLMModelORM
from sqlalchemy import select, update

async def fix_model_names():
    async with AsyncSessionLocal() as session:
        # Update PhoGPT 4B to the community name
        await session.execute(
            update(LLMModelORM)
            .where(LLMModelORM.llm_model_name == "phogpt:4b")
            .values(
                llm_model_name="mantis_lego696/phogpt",
                name="PhoGPT (Community Edition)"
            )
        )
        
        # Remove the 7B one for now if it's not easily available, 
        # or keep it if the user wants to find a specific GGUF later.
        # Let's just keep it as is or update to another community name if known.

        await session.commit()
        print("Updated model names to match Ollama Community library.")

if __name__ == "__main__":
    asyncio.run(fix_model_names())
