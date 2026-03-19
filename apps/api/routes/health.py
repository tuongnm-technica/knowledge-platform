from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from storage.db.db import get_db
from services.llm_service import LLMService
from storage.vector.vector_store import get_qdrant_client
from config.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    status = {}

    try:
        await db.execute(text("SELECT 1"))
        status["postgresql"] = "ok"
    except Exception as e:
        status["postgresql"] = f"error: {e}"

    try:
        client = get_qdrant_client()
        cols = client.get_collections()
        status["qdrant"] = "ok"
        status["qdrant_collections"] = [c.name for c in cols.collections]
    except Exception as e:
        status["qdrant"] = f"error: {e}"

    llm = LLMService()
    ollama_ok = await llm.is_available()
    status["ollama"] = "ok" if ollama_ok else "unavailable — chạy: ollama serve"
    status["ollama_model"] = settings.OLLAMA_LLM_MODEL
    status["embedding_model"] = settings.EMBEDDING_MODEL

    ok = all(status.get(k) == "ok" for k in ["postgresql", "qdrant", "ollama"])
    return {
        "status": "ok" if ok else "degraded",
        "components": status,
        "confluence_url": settings.CONFLUENCE_URL,
        "jira_url": settings.JIRA_URL,
        "confluence_space_keys": settings.CONFLUENCE_SPACE_KEYS,
        "jira_project_keys": settings.JIRA_PROJECT_KEYS,
    }
