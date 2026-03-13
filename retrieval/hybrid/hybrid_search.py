from retrieval.vector.vector_search import VectorSearch
from retrieval.keyword.keyword_search import KeywordSearch
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

log = structlog.get_logger()


class HybridSearch:
    """
    Combine vector search + keyword search dùng Reciprocal Rank Fusion (RRF).

    Điều chỉnh weight:
    - VECTOR_WEIGHT  = 0.5 → semantic (BGE-M3 tiếng Việt tốt)
    - KEYWORD_WEIGHT = 0.5 → exact keyword match (backup cho tên riêng, số, ngày)

    RRF score = vector_w * 1/(k+rank) + keyword_w * 1/(k+rank)
    """

    RRF_K          = 60
    VECTOR_WEIGHT  = 0.5
    KEYWORD_WEIGHT = 0.5

    def __init__(self, session: AsyncSession):
        self._vector  = VectorSearch()
        self._keyword = KeywordSearch(session)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:

        # Chạy song song cả 2
        vector_results  = await self._vector.search(
            query, top_k=top_k * 5, allowed_document_ids=allowed_document_ids
        )
        keyword_results = await self._keyword.search(
            query, top_k=top_k * 5, allowed_document_ids=allowed_document_ids
        )

        log.debug("hybrid_search.raw",
                  vector=len(vector_results),
                  keyword=len(keyword_results))

        return self._rrf_merge(vector_results, keyword_results, top_k)

    def _rrf_merge(
        self,
        vector_results:  list[dict],
        keyword_results: list[dict],
        top_k: int,
    ) -> list[dict]:

        scores: dict[str, float] = {}
        meta:   dict[str, dict]  = {}

        # Vector scores
        for rank, item in enumerate(vector_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0) + \
                self.VECTOR_WEIGHT * (1 / (self.RRF_K + rank + 1))
            item["vector_score"]  = float(item.get("score", 0))
            item["keyword_score"] = 0.0
            meta[cid] = item

        # Keyword scores
        for rank, item in enumerate(keyword_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0) + \
                self.KEYWORD_WEIGHT * (1 / (self.RRF_K + rank + 1))
            if cid in meta:
                meta[cid]["keyword_score"] = float(item.get("score", 0))
            else:
                item["vector_score"]  = 0.0
                item["keyword_score"] = float(item.get("score", 0))
                meta[cid] = item

        ranked  = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for cid, rrf_score in ranked:
            item             = meta[cid]
            item["rrf_score"] = rrf_score
            results.append(item)

        return results