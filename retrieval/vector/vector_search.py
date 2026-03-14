"""
retrieval/vector/vector_search.py
Vector search using Qdrant
"""

from typing import List, Optional

import structlog

from utils.embeddings import get_embedding
from storage.vector.vector_store import get_qdrant

log = structlog.get_logger()

COLLECTION = "knowledge_chunks"


class VectorSearch:

    def __init__(self):

        self.qdrant = get_qdrant()

    async def search(
        self,
        query: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        top_k: int = 20,
        allowed_document_ids: Optional[List[str]] = None,
    ) -> list[dict]:

        try:

            # ─────────────────────────
            # compute embedding if needed
            # ─────────────────────────

            if query_vector is None:

                if query is None:
                    raise ValueError("query or query_vector required")

                query_vector = await get_embedding(query)

            # ─────────────────────────
            # build filter
            # ─────────────────────────

            qfilter = None

            if allowed_document_ids:

                qfilter = {
                    "must": [
                        {
                            "key": "document_id",
                            "match": {"any": allowed_document_ids}
                        }
                    ]
                }

            # ─────────────────────────
            # qdrant search
            # ─────────────────────────

            results = self.qdrant.search(
                collection_name=COLLECTION,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qfilter,
            )

            output = []

            for r in results:

                payload = r.payload or {}

                output.append(
                    {
                        "chunk_id": payload.get("chunk_id"),
                        "document_id": payload.get("document_id"),
                        "content": payload.get("content"),
                        "source": payload.get("source"),
                        "title": payload.get("title"),
                        "score": float(r.score),
                    }
                )

            log.debug(
                "vector_search.done",
                results=len(output),
            )

            return output

        except Exception as e:

            log.error(
                "vector_search.failed",
                error=str(e),
            )

            return []