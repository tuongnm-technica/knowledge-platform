"""
retrieval/vector/vector_search.py
Vector search using Qdrant
"""

from typing import List, Optional

import structlog
from qdrant_client import models

from utils.embeddings import get_embedding
from storage.vector.vector_store import get_qdrant
from config.settings import settings

log = structlog.get_logger()

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
                qfilter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchAny(any=allowed_document_ids)
                        )
                    ]
                )

            # ─────────────────────────
            # qdrant query_points (v1.7+)
            # ─────────────────────────

            results = self.qdrant.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=query_vector,
                limit=top_k,
                query_filter=qfilter,
                with_payload=True,
            ).points

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
                        "url": payload.get("url"),
                        "score": float(r.score or 0.0),
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
