from retrieval.vector.vector_search import VectorSearch
from retrieval.keyword.keyword_search import KeywordSearch
from utils.embeddings import get_embedding

from sqlalchemy.ext.asyncio import AsyncSession

import asyncio
import structlog

log = structlog.get_logger()


class HybridSearch:

    RRF_K = 60
    VECTOR_WEIGHT = 0.6
    KEYWORD_WEIGHT = 0.4

    def __init__(self, session: AsyncSession):

        self._vector = VectorSearch()
        self._keyword = KeywordSearch(session)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:

        try:

            # ─────────────────────────────
            # embed once
            # ─────────────────────────────

            embedding = await get_embedding(query)

            vector_task = self._vector.search(
                query_vector=embedding,
                top_k=50,
                allowed_document_ids=allowed_document_ids,
            )

            keyword_task = self._keyword.search(
                query=query,
                top_k=50,
                allowed_document_ids=allowed_document_ids,
            )

            vector_results, keyword_results = await asyncio.gather(
                vector_task,
                keyword_task,
            )
            # Use per-request weights (don't mutate instance/class state).
            import re
            if re.search(r"\d+/\d+/\d+", query):
                keyword_weight = 0.7
                vector_weight = 0.3
            else:
                keyword_weight = 0.4
                vector_weight = 0.6
                
            log.debug(
                "hybrid_search.raw",
                vector=len(vector_results),
                keyword=len(keyword_results),
            )

            merged = self._rrf_merge(vector_results, keyword_results, vector_weight, keyword_weight)

            return merged[:top_k]

        except Exception as e:

            log.error("hybrid_search.failed", error=str(e))

            return []

    def _rrf_merge(self, vector_results, keyword_results, vector_weight: float, keyword_weight: float):

        scores = {}
        meta = {}

        for rank, item in enumerate(vector_results):

            cid = str(item["chunk_id"])

            score = vector_weight * (1 / (self.RRF_K + rank + 1))

            scores[cid] = scores.get(cid, 0) + score

            item["vector_score"] = float(item.get("score", 0))
            item["keyword_score"] = 0.0

            meta[cid] = item

        for rank, item in enumerate(keyword_results):

            cid = str(item["chunk_id"])

            score = keyword_weight * (1 / (self.RRF_K + rank + 1))

            scores[cid] = scores.get(cid, 0) + score

            if cid in meta:

                meta[cid]["keyword_score"] = float(item.get("score", 0))

            else:

                item["vector_score"] = 0.0
                item["keyword_score"] = float(item.get("score", 0))

                meta[cid] = item

        ranked = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        results = []

        for cid, rrf_score in ranked:

            item = meta[cid]

            item["rrf_score"] = rrf_score

            results.append(item)

        return results
