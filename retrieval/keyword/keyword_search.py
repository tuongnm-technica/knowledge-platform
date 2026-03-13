from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class KeywordSearch:
    """
    Keyword search dùng PostgreSQL full-text search.
    Dùng 'simple' config thay vì 'english' để hỗ trợ tiếng Việt.
    'simple' chỉ lowercase + tokenize, không stem — phù hợp tiếng Việt.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:

        # Build tsquery — thử websearch_to_tsquery trước (tolerant hơn)
        # websearch_to_tsquery tự xử lý stop words, special chars
        # Fallback: plainto_tsquery nếu query có ký tự đặc biệt
        ts_query = self._build_tsquery(query)

        base_sql = """
            SELECT
                c.id           AS chunk_id,
                c.document_id,
                c.content,
                c.chunk_index,
                ts_rank_cd(
                    to_tsvector('simple', c.content),
                    {tsquery_expr}
                ) AS score
            FROM chunks c
            WHERE
                {filter_clause}
                to_tsvector('simple', c.content) @@ {tsquery_expr}
            ORDER BY score DESC
            LIMIT :top_k
        """

        tsquery_expr  = "websearch_to_tsquery('simple', :q)"
        filter_clause = "c.document_id = ANY(:doc_ids) AND " if allowed_document_ids else ""

        sql = base_sql.format(
            tsquery_expr=tsquery_expr,
            filter_clause=filter_clause,
        )

        params = {"q": query, "top_k": top_k}
        if allowed_document_ids:
            params["doc_ids"] = allowed_document_ids

        try:
            result = await self._session.execute(text(sql), params)
            rows   = result.mappings().all()
            results = [dict(r) for r in rows]
        except Exception:
            # Fallback: plainto_tsquery
            fallback_sql = base_sql.format(
                tsquery_expr="plainto_tsquery('simple', :q)",
                filter_clause=filter_clause,
            )
            try:
                result = await self._session.execute(text(fallback_sql), params)
                rows   = result.mappings().all()
                results = [dict(r) for r in rows]
            except Exception:
                results = []

        # ILIKE fallback — đảm bảo luôn có kết quả khi FTS miss
        # (FTS với tiếng Việt đôi khi không match do tokenization)
        if not results:
            results = await self._ilike_search(query, top_k, allowed_document_ids)

        return results

    async def _ilike_search(
        self,
        query: str,
        top_k: int,
        allowed_document_ids: list[str] | None,
    ) -> list[dict]:
        """ILIKE fallback — tìm từng từ trong query, OR logic."""
        import re
        # Lấy các từ có nghĩa (>= 2 ký tự)
        words = [w for w in re.split(r"\s+", query.strip()) if len(w) >= 2]
        if not words:
            return []

        conditions = " OR ".join([f"c.content ILIKE :w{i}" for i in range(len(words))])
        filter_clause = "c.document_id = ANY(:doc_ids) AND " if allowed_document_ids else ""

        sql = f"""
            SELECT
                c.id           AS chunk_id,
                c.document_id,
                c.content,
                c.chunk_index,
                0.1            AS score
            FROM chunks c
            WHERE {filter_clause} ({conditions})
            ORDER BY c.id
            LIMIT :top_k
        """
        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        params["top_k"] = top_k
        if allowed_document_ids:
            params["doc_ids"] = allowed_document_ids

        try:
            result = await self._session.execute(text(sql), params)
            rows   = result.mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _build_tsquery(self, query: str) -> str:
        """Normalize query — bỏ ký tự đặc biệt gây lỗi tsquery"""
        import re
        return re.sub(r"[^\w\s]", " ", query).strip()