"""
orchestration/tools/search.py
"""
orchestration/tools/search.py
Tools tìm kiếm tách biệt theo nguồn:
  search_confluence / search_jira / search_slack / search_files / search_all
"""
import json
import re

from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from config.settings import settings
from services.rag_service import RAGService


log = structlog.get_logger()


# ─────────────────────────────────────────
# Base Search Tool
# ─────────────────────────────────────────

class _BaseSearchTool(BaseTool):

    def __init__(self, session: AsyncSession):
        self._rag = None
        self._session = session


    async def _do_search(
        self,
        query: str,
        source_filter: str,
        limit: int,
        user_id: str,
    ) -> ToolResult:

        try:
            if not self._rag:
                self._rag = RAGService(self._session, user_id)

            try:
                limit = int(limit)
            except Exception:
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
