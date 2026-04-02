
import asyncio
import structlog
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal
from tasks.pm_metrics import aggregate_pm_metrics

log = structlog.get_logger()

async def trigger_full_aggregation():
    async with AsyncSessionLocal() as session:
        print("Fetching unique project keys from documents...")
        query = text("SELECT DISTINCT metadata->>'project_key' FROM documents WHERE source = 'jira' AND metadata->>'project_key' IS NOT NULL")
        res = await session.execute(query)
        projects = [r[0] for r in res.fetchall() if r[0]]
        
        print(f"Found {len(projects)} projects: {projects}")
        
        for project in projects:
            print(f"Aggregating metrics for project: {project}")
            try:
                # aggregate_pm_metrics handles its own commit
                await aggregate_pm_metrics(session, project)
                print(f"  Successfully aggregated {project}")
            except Exception as e:
                print(f"  Failed to aggregate {project}: {str(e)}")
        
        # Finally, run a global aggregation or ensure the project_insights/daily tables are full
        print("Aggregation complete.")

if __name__ == "__main__":
    asyncio.run(trigger_full_aggregation())
