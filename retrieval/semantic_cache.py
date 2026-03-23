"""
Semantic cache for RAG answers
"""

import hashlib
from typing import Optional

from utils.embeddings import get_embedding
from storage.vector.vector_store import get_qdrant

COLLECTION = "semantic_cache"


class SemanticCache:

    def __init__(self):

        self.qdrant = get_qdrant()


    async def lookup(self, query: str, threshold: float | None = None) -> Optional[str]:
        if threshold is None:
            from config.settings import settings
            threshold = settings.SEMANTIC_CACHE_THRESHOLD

        vector = await get_embedding(query)

        res = self.qdrant.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=1,
        ).points

        if not res:
            return None

        hit = res[0]

        if hit.score < threshold:
            return None

        payload = hit.payload or {}

        return payload.get("answer")


    async def store(self, query: str, answer: str):

        vector = await get_embedding(query)

        key = hashlib.md5(query.encode()).hexdigest()

        self.qdrant.upsert(
            collection_name=COLLECTION,
            points=[
                {
                    "id": key,
                    "vector": vector,
                    "payload": {
                        "query": query,
                        "answer": answer,
                    },
                }
            ],
        )