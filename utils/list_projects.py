import asyncio
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from utils.logger_config import configure_logging
from config.settings import settings

configure_logging(debug=settings.DEBUG)

async def list_projects():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT DISTINCT metadata->>'project_key' as pk FROM documents WHERE source = 'jira'"))
        projects = [row[0] for row in res.fetchall() if row[0]]
        print(f"Project Keys in DB: {projects}")

if __name__ == "__main__":
    asyncio.run(list_projects())
