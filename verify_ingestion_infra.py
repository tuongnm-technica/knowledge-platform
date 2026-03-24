import asyncio
import os
import sys
import httpx
from arq.connections import create_pool, RedisSettings

# Add current dir to path to import settings
sys.path.append(os.getcwd())
from config.settings import settings

async def check_redis():
    print(f"Checking Redis connection to: {settings.REDIS_URL} ...")
    try:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        pool = await create_pool(redis_settings)
        await pool.ping()
        print("✅ Redis connection successful!")
        await pool.close()
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Advice: If running locally, check if REDIS_URL should be 'redis://localhost:6379/0'")

async def check_ollama():
    print(f"Checking Ollama connection to: {settings.OLLAMA_BASE_URL} ...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = [m['name'] for m in resp.json().get('models', [])]
            print(f"✅ Ollama connection successful! Models available: {models}")
            
            vision_model = settings.OLLAMA_VISION_MODEL
            if vision_model in models or any(vision_model in m for m in models):
                print(f"✅ Vision model '{vision_model}' found.")
            else:
                print(f"⚠️ Vision model '{vision_model}' NOT found in Ollama. Ingestion will skip image description.")
    except Exception as e:
        print(f"❌ Ollama connection failed: {e}")

async def main():
    print("--- Ingestion Infrastructure Verification ---\n")
    await check_redis()
    print("-" * 40)
    await check_ollama()
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
