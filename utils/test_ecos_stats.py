import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from utils.logger_config import configure_logging
from config.settings import settings

configure_logging(debug=settings.DEBUG)

async def test_stats():
    async with AsyncSessionLocal() as session:
        # Test Case: ECOS2025
        res = await session.execute(text("SELECT COUNT(*) FROM documents WHERE source = 'jira' AND (metadata->>'project_key' ILIKE 'ECOS2025' OR metadata->>'project_key' ILIKE '[ECOS2025]')"))
        print(f"Stats for 'ECOS2025': {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(test_stats())
