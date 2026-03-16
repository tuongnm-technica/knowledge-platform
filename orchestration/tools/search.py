"""
orchestration/tools/search.py
Tools tìm kiếm tách biệt theo nguồn:
  search_confluence / search_jira / search_slack / search_files / search_all
"""
import json

from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from retrieval.hybrid.hybrid_search import HybridSearch
from permissions.filter import PermissionFilter
from ranking.scorer import RankingScorer
from persistence.document_repository import DocumentRepository

from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from retrieval.query_router import route_query_advanced
from retrieval.query_expansion import expand_query
from retrieval.reranker import rerank
from config.settings import settings
from connectors.slack.utils import slack_deep_link
log = structlog.get_logger()


def _jsonish(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) if value else {}
        except Exception:
            return {}
    return {}


# ─────────────────────────────────────────
# Base Search Tool
# ─────────────────────────────────────────

class _BaseSearchTool(BaseTool):

    def __init__(self, session: AsyncSession):

        self._search      = HybridSearch(session)
        self._permissions = PermissionFilter(session)
        self._scorer      = RankingScorer()
        self._repo        = DocumentRepository(session)


    async def _do_search(
        self,
        query: str,
        source_filter: str,
        limit: int,
        user_id: str,
    ) -> ToolResult:

        try:
            try:
                limit = int(limit)
            except Exception:
                limit = 5

            allowed_ids = (
                await self._permissions.allowed_docs(user_id)
                if user_id else None
            )
            if allowed_ids is not None and len(allowed_ids) == 0:
                return ToolResult(
                    success=True,
                    data=[],
                    summary="Khong co tai lieu nao ban duoc phep truy cap trong he thong.",
                )

            # fetch nhiều hơn để ranking sau filter
            fetch_k = max(limit * 8, 20)
            queries = await expand_query(query, use_llm=settings.QUERY_EXPANSION_ENABLED)
            raw = []
            for q in queries:

                res = await self._search.search(
                    q,
                    top_k=fetch_k,
                    allowed_document_ids=allowed_ids,
                )

                raw.extend(res)
                seen = set()
                unique = []

                for r in raw:
                    cid = r.get("chunk_id")

                    if cid not in seen:
                        seen.add(cid)
                        unique.append(r)

                raw = unique

            # source filter
            if source_filter != "all":
                raw = [
                    r for r in raw
                    if r.get("source", "") == source_filter
                ]

            if not raw:

                return ToolResult(
                    success=True,
                    data=[],
                    summary=f"Không tìm thấy kết quả nào trong [{source_filter.upper()}] cho: '{query}'",
                )

            # load document metadata
            doc_ids = list({str(r["document_id"]) for r in raw})

            rows = await self._repo.get_by_ids(doc_ids)

            doc_meta = {r["id"]: r for r in rows}

            # Provide query string for ranking signals (e.g., title match boost).
            for item in raw:
                item["query"] = query

            scored = self._scorer.score(raw, doc_meta)
            shortlist_n = min(max(limit * 4, 12), 40)
            shortlist = scored[:shortlist_n]

            if settings.RERANKING_ENABLED:
                shortlist = await rerank(
                    query=query,
                    candidates=shortlist,
                    top_k=limit,
                )
            else:
                shortlist = shortlist[:limit]

            results = []

            # ─────────────────────────────────────
            # build result objects
            # ─────────────────────────────────────

            for item in shortlist:

                doc_id = str(item.get("document_id", ""))

                meta = doc_meta.get(doc_id, {})

                chunk_id = str(item.get("chunk_id", ""))

                context_text = item.get("content", "")

                # load neighbor chunks for context window
                try:

                    neighbors = await self._repo.get_neighbor_chunks(
                        chunk_id,
                        window=5
                    )

                    if neighbors:
                        context_text = "\n".join(
                            [c["content"] for c in neighbors]
                        )

                except Exception:
                    pass

                url = meta.get("url", "")
                if meta.get("source") == "slack" and context_text:
                    import re
                    m = re.search(r"^\[\d{2}:\d{2}\|([0-9]+\.[0-9]+)\]", context_text, re.MULTILINE)
                    md = _jsonish(meta.get("metadata"))
                    channel_id = str(md.get("channel_id") or "").strip()
                    if channel_id and m:
                        url = slack_deep_link(channel_id, m.group(1))

                results.append({
                    "document_id": doc_id,
                    "chunk_id": chunk_id,
                    "title": meta.get("title", "Untitled"),
                    "source": meta.get("source", source_filter),
                    "url": url,
                    "content": context_text,
                    "snippet": (context_text or "")[:350],
                    "score": round(item.get("rerank_score", item.get("final_score", 0)), 3),
                })


            # ─────────────────────────────────────
            # BUILD LLM OBSERVATION
            # ─────────────────────────────────────

            lines = []

            lines.append(
                f"[{source_filter.upper()} RESULTS] "
                f"{len(results)} kết quả cho query: '{query}'"
            )

            for i, r in enumerate(results, 1):

                content = r["content"].strip()

                lines.append(
                    f"""
Result {i}
SOURCE: {r["source"]}
TITLE: {r["title"]}
SCORE: {r["score"]}

CONTENT:
{content}
""".strip()
                )

            summary = "\n\n".join(lines)


            log.info(
                "tool.search",
                source=source_filter,
                query=query[:60],
                found=len(results),
            )

            return ToolResult(
                success=True,
                data=results,
                summary=summary,
            )


        except Exception as e:

            log.error(
                "tool.search.error",
                source=source_filter,
                error=str(e),
            )

            return ToolResult(
                success=False,
                data=[],
                summary="",
                error=str(e),
            )


# ─────────────────────────────────────────
# Confluence Search
# ─────────────────────────────────────────

class SearchConfluenceTool(_BaseSearchTool):

    @property
    def spec(self) -> ToolSpec:

        return ToolSpec(
            name="search_confluence",
            description="Tìm tài liệu kỹ thuật, specs, quy trình, API docs trong Confluence.",
            parameters={
                "query": "Câu truy vấn",
                "limit": "Số kết quả (mặc định: 5)"
            },
        )

    async def run(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "",
        **_
    ) -> ToolResult:

        return await self._do_search(query, "confluence", limit, user_id)


# ─────────────────────────────────────────
# Jira Search
# ─────────────────────────────────────────

class SearchJiraTool(_BaseSearchTool):

    @property
    def spec(self) -> ToolSpec:

        return ToolSpec(
            name="search_jira",
            description="Tìm Jira issues, bugs, tasks theo từ khóa trong knowledge base đã index.",
            parameters={
                "query": "Tên bug, feature, component cần tìm",
                "limit": "Số kết quả (mặc định: 5)",
            },
        )

    async def run(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "",
        **_
    ) -> ToolResult:

        return await self._do_search(query, "jira", limit, user_id)


# ─────────────────────────────────────────
# Slack Search
# ─────────────────────────────────────────

class SearchSlackTool(_BaseSearchTool):

    @property
    def spec(self) -> ToolSpec:

        return ToolSpec(
            name="search_slack",
            description=(
                "Tìm nội dung Slack đã sync vào knowledge base. "
                "Dùng cho meeting notes, thảo luận cũ, quyết định."
            ),
            parameters={
                "query": "Nội dung cần tìm trong Slack",
                "limit": "Số kết quả (mặc định: 5)",
            },
        )

    async def run(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "",
        **_
    ) -> ToolResult:

        return await self._do_search(query, "slack", limit, user_id)


# ─────────────────────────────────────────
# File Search
# ─────────────────────────────────────────

class SearchFilesTool(_BaseSearchTool):

    @property
    def spec(self) -> ToolSpec:

        return ToolSpec(
            name="search_files",
            description="Tìm trong file server (docx, xlsx, pdf, pptx).",
            parameters={
                "query": "Tên file hoặc nội dung",
                "limit": "Số kết quả (mặc định: 5)",
            },
        )

    async def run(
        self,
        query: str,
        limit: int = 5,
        user_id: str = "",
        **_
    ) -> ToolResult:

        return await self._do_search(query, "file_server", limit, user_id)


# ─────────────────────────────────────────
# Search All
# ─────────────────────────────────────────

class SearchAllTool(_BaseSearchTool):

    @property
    def spec(self) -> ToolSpec:

        return ToolSpec(
            name="search_all",
            description="Tìm toàn bộ knowledge base khi không chắc thông tin nằm ở nguồn nào.",
            parameters={
                "query": "Câu truy vấn",
                "limit": "Số kết quả (mặc định: 8)",
            },
        )

    async def run(
        self,
        query: str,
        limit: int = 8,
        user_id: str = "",
        **_
    ) -> ToolResult:
        source = route_query_advanced(query)
        log.info("query_router", query=query, routed_source=source)
        return await self._do_search(query, source, limit, user_id)
