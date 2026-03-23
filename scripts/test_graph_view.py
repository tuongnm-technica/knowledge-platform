import asyncio
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from graph.graph_view import GraphViewBuilder

DATABASE_URL = "postgresql+asyncpg://postgres:Abcd%401234%21@host.docker.internal:5432/knowledge_platform"

async def run():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        # We need a session for GraphViewBuilder
        from sqlalchemy.orm import sessionmaker
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            builder = GraphViewBuilder(session)
            resp = await builder.build_overview(since_days=30)
            print(json.dumps({
                "nodes_count": len(resp["detail"]["nodes"]),
                "edges_count": len(resp["detail"]["edges"]),
                "super_nodes_count": len(resp["super"]["nodes"]),
                "super_edges_count": len(resp["super"]["edges"]),
                "insights_count": len(resp["insights"])
            }, indent=2))
            
            if resp["detail"]["nodes"]:
                print("\nSample Node:", resp["detail"]["nodes"][0])
            if resp["detail"]["edges"]:
                print("\nSample Edge:", resp["detail"]["edges"][0])

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
