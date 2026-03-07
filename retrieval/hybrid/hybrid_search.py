from retrieval.vector.vector_search import VectorSearch
from retrieval.keyword.keyword_search import KeywordSearch
from sqlalchemy.ext.asyncio import AsyncSession


class HybridSearch:
    RRF_K = 60

    def __init__(self, session: AsyncSession):
        self._vector = VectorSearch()
        self._keyword = KeywordSearch(session)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:
        vector_results = await self._vector.search(query, top_k=top_k * 2, allowed_document_ids=allowed_document_ids)
        keyword_results = await self._keyword.search(query, top_k=top_k * 2, allowed_document_ids=allowed_document_ids)
        return self._rrf_merge(vector_results, keyword_results, top_k)

    def _rrf_merge(self, vector_results, keyword_results, top_k):
        scores: dict[str, float] = {}
        meta: dict[str, dict] = {}

        for rank, item in enumerate(vector_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0) + 1 / (self.RRF_K + rank + 1)
            item["vector_score"] = float(item.get("score", 0))
            item["keyword_score"] = 0.0
            meta[cid] = item

        for rank, item in enumerate(keyword_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0) + 1 / (self.RRF_K + rank + 1)
            if cid in meta:
                meta[cid]["keyword_score"] = float(item.get("score", 0))
            else:
                item["vector_score"] = 0.0
                item["keyword_score"] = float(item.get("score", 0))
                meta[cid] = item

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [dict(meta[cid], rrf_score=rrf_score) for cid, rrf_score in ranked]