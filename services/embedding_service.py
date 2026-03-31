import asyncio
import structlog
from typing import List
from services.llm_service import LLMService
from utils.embedding_cache import get_embedding_cached, set_embedding_cached

log = structlog.get_logger(__name__)

class EmbeddingService:
    def __init__(self, llm_service: LLMService = None):
        # Use LLMService with task_type="embedding" to resolve model from DB
        self._llm = llm_service or LLMService(task_type="embedding")
    
    async def get_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        if not text:
            return []

        if use_cache:
            cached = await get_embedding_cached(text)
            if cached is not None:
                return cached
        
        vector = await self._llm.embed(text)
        
        # LLMService.embed returns List[float] for single string or List[List[float]] for list
        if isinstance(vector, list) and len(vector) > 0 and isinstance(vector[0], list):
            vector = vector[0]

        if use_cache and vector:
            await set_embedding_cached(text, vector)
        
        return vector

    async def get_embeddings_batch(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        if not texts:
            return []

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
            
            # Delegate batch embedding to LLMService (which delegates to provider)
            vectors = await self._llm.embed(uncached_texts)
            
            if not isinstance(vectors, list) or len(vectors) != len(uncached_texts):
                log.error("embedding_service.size_mismatch", expected=len(uncached_texts), got=len(vectors) if isinstance(vectors, list) else "not a list")
                raise ValueError(f"Embedding provider returned unexpected result for {len(uncached_texts)} texts")

            for i, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                results[idx] = vectors[i]
                if use_cache:
                    await set_embedding_cached(text, vectors[i])

        # Verification: ensure all slots are filled.
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
