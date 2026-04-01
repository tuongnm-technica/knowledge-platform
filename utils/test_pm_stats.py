import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from utils.logger_config import configure_logging

from config.settings import settings

# Khởi tạo logging sớm như trong server.py / arq_worker.py
configure_logging(debug=settings.DEBUG)

async def test_stats():
    async with AsyncSessionLocal() as session:
        # Test Case: Project Key 'KP' (hoàn toàn khớp)
        res = await session.execute(text("SELECT COUNT(*) FROM documents WHERE source = 'jira' AND (metadata->>'project' ILIKE 'KP' OR metadata->>'project' ILIKE '[KP]')"))
        print(f"Stats for 'KP': {res.scalar()}")

        # Test Case: Project Key 'kp' (viết thường - trước đây sẽ về 0)
        res = await session.execute(text("SELECT COUNT(*) FROM documents WHERE source = 'jira' AND (metadata->>'project' ILIKE 'kp' OR metadata->>'project' ILIKE '[kp]')"))
        print(f"Stats for 'kp': {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(test_stats())
