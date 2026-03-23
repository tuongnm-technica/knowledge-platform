import asyncio
import httpx
import structlog
from typing import Protocol, List
from config.settings import settings
from utils.embedding_cache import get_embedding_cached, set_embedding_cached

log = structlog.get_logger(__name__)

class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> List[float]:
        ...
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...

class OllamaEmbeddingProvider:
    def __init__(self):
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_EMBED_MODEL
        self._client = httpx.AsyncClient(timeout=300)
    
    async def embed(self, text: str) -> List[float]:
        resp = await self._client.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings") or data.get("embedding")
        if isinstance(embeddings[0], list):
            return embeddings[0]
        return embeddings

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Limit concurrency
        semaphore = asyncio.Semaphore(settings.EMBEDDING_CONCURRENCY)
        
        async def _limited_embed(text: str):
            async with semaphore:
                return await self.embed(text)
        
        return await asyncio.gather(*[_limited_embed(t) for t in texts])

class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider = None):
        self._provider = provider or OllamaEmbeddingProvider()
    
    async def get_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        if use_cache:
            cached = await get_embedding_cached(text)
            if cached is not None:
                return cached
        
        vector = await self._provider.embed(text)
        
        if use_cache:
            await set_embedding_cached(text, vector)
        
        return vector

    async def get_embeddings_batch(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        results: List[List[float] | None] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        if use_cache:
            for i, text in enumerate(texts):
                cached = await get_embedding_cached(text)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        if uncached_texts:
            log.debug("embedding_service.batch", total=len(texts), uncached=len(uncached_texts))
            vectors = await self._provider.embed_batch(uncached_texts)
            
            if len(vectors) != len(uncached_texts):
                log.error("embedding_service.size_mismatch", expected=len(uncached_texts), got=len(vectors))
                raise ValueError(f"Embedding provider returned {len(vectors)} vectors for {len(uncached_texts)} texts")

            for i, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                results[idx] = vectors[i]
                if use_cache:
                    await set_embedding_cached(text, vectors[i])

        # Pre-allocation check: ensure all slots are filled. 
        # If any slot is None, it means something went wrong in the batch logic.
        final_results = []
        for v in results:
            if v is None:
                raise ValueError("Incomplete embedding batch results. Alignment could be broken.")
            final_results.append(v)
            
        return final_results

# Singleton instance
_service = None

def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service
