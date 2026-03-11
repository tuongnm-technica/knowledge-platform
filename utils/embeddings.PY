"""
Embedding via Ollama BGE-M3 (on-premise).
Không dùng sentence-transformers hay HuggingFace.
"""

import httpx
from config.settings import settings
import structlog

log = structlog.get_logger()


def get_embedding_sync(text: str) -> list[float]:
    """Gọi Ollama embedding API đồng bộ — dùng cho query."""
    response = httpx.post(
        f"{settings.OLLAMA_BASE_URL}/api/embed",
        json={
            "model": settings.OLLAMA_EMBED_MODEL,
            "input": text,
        },
        timeout=360,
    )
    response.raise_for_status()
    return response.json()["embeddings"][0]


async def get_embedding(text: str) -> list[float]:
    """Async embedding — dùng cho query trong search pipeline."""
    async with httpx.AsyncClient(timeout=360) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.OLLAMA_EMBED_MODEL,
                "input": text,
            },
        )
        response.raise_for_status()
        return response.json()["embeddings"][0]


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding — dùng khi index chunks."""
    if not texts:
        return []

    log.info("embedding.batch.start", count=len(texts), model=settings.OLLAMA_EMBED_MODEL)

    batch_size  = 32
    all_vectors = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "input": batch,
                },
                timeout=360,
            )
            response.raise_for_status()
            all_vectors.extend(response.json()["embeddings"])
            log.info("embedding.batch.progress", done=i + len(batch), total=len(texts))
        except Exception as e:
            log.error("embedding.batch.error", batch_start=i, error=str(e))
            raise

    return all_vectors