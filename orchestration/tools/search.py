"""
orchestration/tools/search.py
Tools tìm kiếm tách biệt theo nguồn:
  search_confluence / search_jira / search_slack / search_files / search_all
"""
from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from retrieval.hybrid.hybrid_search import HybridSearch
from permissions.filter import PermissionFilter
from ranking.scorer import RankingScorer
from persistence.document_repository import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

log = structlog.get_logger()


class _BaseSearchTool(BaseTool):
    def __init__(self, session: AsyncSession):
        self._search      = HybridSearch(session)
        self._permissions = PermissionFilter(session)
        self._scorer      = RankingScorer()
        self._repo        = DocumentRepository(session)

    async def _do_search(self, query: str, source_filter: str,
                          limit: int, user_id: str) -> ToolResult:
        try:
            allowed_ids = await self._permissions.allowed_docs(user_id) if user_id else None
            # Khi filter theo source, lấy nhiều hơn để tránh bị lọc hết
            fetch_k = limit * 3 if source_filter == "all" else limit * 10
            raw = await self._search.search(
                query, top_k=fetch_k, allowed_document_ids=allowed_ids,
            )
            if source_filter != "all":
                raw = [r for r in raw if r.get("source", "") == source_filter]

            if not raw:
                return ToolResult(success=True, data=[],
                    summary=f"Không tìm thấy kết quả nào trong [{source_filter.upper()}] cho: '{query}'")

            doc_ids  = list({str(r["document_id"]) for r in raw})
            rows     = await self._repo.get_by_ids(doc_ids)
            doc_meta = {r["id"]: r for r in rows}
            scored   = self._scorer.score(raw, doc_meta)[:limit]

            results = []
            for item in scored:
                doc_id = str(item.get("document_id", ""))
                meta   = doc_meta.get(doc_id, {})
                results.append({
                    "document_id": doc_id,
                    "title":   meta.get("title", "Untitled"),
                    "source":  meta.get("source", source_filter),
                    "url":     meta.get("url", ""),
                    "content": item.get("content", "")[:400],
                    "score":   round(item.get("final_score", 0), 3),
                })

            lines = [f"[{source_filter.upper()}] Tìm thấy {len(results)} kết quả cho '{query}':"]
            for i, r in enumerate(results, 1):
                lines.append(f"  [{i}] {r['title']} (score:{r['score']})\n      {r['content'][:200]}...")

            log.info("tool.search", source=source_filter, query=query[:60], found=len(results))
            return ToolResult(success=True, data=results, summary="\n".join(lines))

        except Exception as e:
            log.error("tool.search.error", source=source_filter, error=str(e))
            return ToolResult(success=False, data=[], summary="", error=str(e))


class SearchConfluenceTool(_BaseSearchTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_confluence",
            description="Tìm tài liệu kỹ thuật, specs, quy trình, API docs trong Confluence.",
            parameters={"query": "Câu truy vấn", "limit": "Số kết quả (mặc định: 5)"},
        )
    async def run(self, query: str, limit: int = 5, user_id: str = "", **_) -> ToolResult:
        return await self._do_search(query, "confluence", limit, user_id)


class SearchJiraTool(_BaseSearchTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_jira",
            description="Tìm Jira issues, bugs, tasks theo từ khóa trong knowledge base đã index.",
            parameters={"query": "Tên bug, feature, component cần tìm", "limit": "Số kết quả (mặc định: 5)"},
        )
    async def run(self, query: str, limit: int = 5, user_id: str = "", **_) -> ToolResult:
        return await self._do_search(query, "jira", limit, user_id)


class SearchSlackTool(_BaseSearchTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_slack",
            description=("Tìm kiếm nội dung Slack đã được sync vào knowledge base (Confluence, Jira, Slack, Files). "
                "Dùng cho: meeting notes, thảo luận cũ, quyết định, nội dung từ ngày hôm qua trở về trước. "
                "Tốt hơn get_slack_messages khi tìm theo chủ đề/từ khóa thay vì channel cụ thể."),
            parameters={"query": "Nội dung cần tìm trong Slack", "limit": "Số kết quả (mặc định: 5)"},
        )
    async def run(self, query: str, limit: int = 5, user_id: str = "", **_) -> ToolResult:
        return await self._do_search(query, "slack", limit, user_id)


class SearchFilesTool(_BaseSearchTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_files",
            description="Tìm trong file server (docx, xlsx, pdf, pptx). Dùng khi cần báo cáo, template.",
            parameters={"query": "Tên file hoặc nội dung", "limit": "Số kết quả (mặc định: 5)"},
        )
    async def run(self, query: str, limit: int = 5, user_id: str = "", **_) -> ToolResult:
        return await self._do_search(query, "file_server", limit, user_id)


class SearchAllTool(_BaseSearchTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_all",
            description="Tìm toàn bộ knowledge base khi không chắc thông tin nằm ở nguồn nào.",
            parameters={"query": "Câu truy vấn", "limit": "Số kết quả (mặc định: 8)"},
        )
    async def run(self, query: str, limit: int = 8, user_id: str = "", **_) -> ToolResult:
        return await self._do_search(query, "all", limit, user_id)