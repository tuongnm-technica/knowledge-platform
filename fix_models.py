import asyncio
import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

async def fix_models():
    from storage.db.db import reset_llm_models_to_defaults
    print("Running reset_llm_models_to_defaults...")
    await reset_llm_models_to_defaults()
    print("SUCCESS: Reset completed")

if __name__ == "__main__":
    asyncio.run(fix_models())
