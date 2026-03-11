from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from storage.db.db import get_db
from storage.vector.vector_store import VectorStore
from config.settings import settings
import httpx
import structlog

log = structlog.get_logger()
router = APIRouter()


async def get_doc_count(session: AsyncSession, source: str) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM documents WHERE source = :source"),
        {"source": source}
    )
    return result.scalar() or 0


async def get_chunk_count(session: AsyncSession, source: str) -> int:
    result = await session.execute(
        text("""
            SELECT COUNT(*) FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.source = :source
        """),
        {"source": source}
    )
    return result.scalar() or 0


async def get_last_sync(session: AsyncSession, source: str) -> str:
    result = await session.execute(
        text("""
            SELECT MAX(updated_at) FROM documents WHERE source = :source
        """),
        {"source": source}
    )
    val = result.scalar()
    return val.strftime("%d/%m/%Y %H:%M") if val else "Chưa sync"


@router.get("/connectors/stats")
async def get_connector_stats(session: AsyncSession = Depends(get_db)):
    sources = ["confluence", "jira", "slack"]
    stats = {}

    for source in sources:
        docs   = await get_doc_count(session, source)
        chunks = await get_chunk_count(session, source)
        last   = await get_last_sync(session, source)
        stats[source] = {
            "documents": docs,
            "chunks":    chunks,
            "last_sync": last,
            "status":    "idle" if docs > 0 else "empty",
        }

    return {"stats": stats}