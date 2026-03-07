from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class KeywordSearch:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:
        ts_query = " & ".join(q for q in query.split() if q)

        if allowed_document_ids:
            result = await self._session.execute(
                text("""
                    SELECT c.id AS chunk_id, c.document_id, c.content, c.chunk_index,
                        ts_rank(to_tsvector('english', c.content), to_tsquery('english', :q)) AS score
                    FROM chunks c
                    WHERE c.document_id = ANY(:doc_ids)
                      AND to_tsvector('english', c.content) @@ to_tsquery('english', :q)
                    ORDER BY score DESC LIMIT :top_k
                """),
                {"q": ts_query, "doc_ids": allowed_document_ids, "top_k": top_k},
            )
        else:
            result = await self._session.execute(
                text("""
                    SELECT c.id AS chunk_id, c.document_id, c.content, c.chunk_index,
                        ts_rank(to_tsvector('english', c.content), to_tsquery('english', :q)) AS score
                    FROM chunks c
                    WHERE to_tsvector('english', c.content) @@ to_tsquery('english', :q)
                    ORDER BY score DESC LIMIT :top_k
                """),
                {"q": ts_query, "top_k": top_k},
            )

        rows = result.mappings().all()
        return [
            {**dict(r), "vector_score": 0.0, "keyword_score": float(r["score"])}
            for r in rows
        ]