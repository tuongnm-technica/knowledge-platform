"""
utils/embeddings.py
────────────────────
On-Premise Embedding via Ollama BGE-M3.
Tích hợp cache để tránh gọi Ollama lặp lại cho cùng 1 text.

Cache hit rate ~30-40% trong thực tế → giảm ~300-500ms latency mỗi request.
"""
from __future__ import annotations
import asyncio
import httpx
import structlog
from config.settings import settings
from utils.embedding_cache import get_embedding_cached, set_embedding_cached, get_cache_stats

log = structlog.get_logger()


async def get_embedding(text: str) -> list[float]:
    """
    Async embedding với cache.
    Cache hit  → trả về ngay (~0ms)
    Cache miss → gọi Ollama BGE-M3 (~300-500ms)
    """
    # 1. Check cache
    cached = await get_embedding_cached(text)
    if cached is not None:
        return cached

    # 2. Call Ollama
    vector = await _call_ollama_embed(text)

    # 3. Store in cache
    await set_embedding_cached(text, vector)
    return vector


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Batch embedding với cache per-item.
    Items đã có trong cache → không gọi Ollama.
    Items chưa có → gọi Ollama batch 1 lần.
    """
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts:   list[str] = []

    # Check cache cho từng text
    for i, text in enumerate(texts):
        cached = await get_embedding_cached(text)
        if cached is not None:
            results[i] = cached
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if uncached_texts:
        log.debug("embeddings.batch", total=len(texts), uncached=len(uncached_texts))
        # Gọi Ollama cho phần chưa cache
        vectors = await _call_ollama_embed_batch(uncached_texts)
        for i, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
            results[idx] = vectors[i]
            await set_embedding_cached(text, vectors[i])

    return [r for r in results if r is not None]


# ─── Ollama API calls ─────────────────────────────────────────────────────────

async def _call_ollama_embed(text: str) -> list[float]:
    """Single embedding call to Ollama."""
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    model = settings.OLLAMA_EMBED_MODEL

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{base}/api/embed",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama /api/embed trả về {"embeddings": [[...]]}
        embeddings = data.get("embeddings") or data.get("embedding")
        if isinstance(embeddings[0], list):
            return embeddings[0]
        return embeddings


async def _call_ollama_embed_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding — gọi từng text nhưng concurrent."""
    tasks = [_call_ollama_embed(t) for t in texts]
    # Giới hạn concurrency để không quá tải Ollama
    semaphore = asyncio.Semaphore(4)

    async def _limited(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*[_limited(t) for t in tasks])


def get_embedding_stats() -> dict:
    """Trả về cache stats — hiện qua /health endpoint."""
    return get_cache_stats()