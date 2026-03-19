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
                limit = 5

            results = await self._rag.searchv2(
                query_text=query,
                limit=limit,
                source=source_filter,
                expand=settings.QUERY_EXPANSION_ENABLED,
                use_rerank=settings.RERANKING_ENABLED,
                include_context=True,
                context_window=5
            )

            if not results:
                return ToolResult(
                    success=True,
                    data=[],
                    summary=f"Không tìm thấy kết quả nào trong [{source_filter.upper()}] cho: '{query}'",
                )

            # BUILD LLM OBSERVATION
            lines = [
                f"[{source_filter.upper()} RESULTS] "
                f"{len(results)} kết quả cho query: '{query}'"
            ]

            for i, r in enumerate(results, 1):
                content = r.get("content", "").strip()
                lines.append(
                    f"Result {i}\nSOURCE: {r['source']}\nTITLE: {r['title']}\nSCORE: {r['score']}\n\nCONTENT:\n{content}"
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
            log.exception("tool.search.error", source=source_filter, error=str(e))
            return ToolResult(success=False, data=[], summary="", error=str(e))


class ConfluenceSearchTool(_BaseSearchTool):
    spec = ToolSpec(
        name="search_confluence",
        description="Tìm kiếm kiến thức trong Confluence (Wiki, Documentation, Quy trình).",
        parameters={
            "query": "Từ khóa tìm kiếm.",
            "limit": "Số lượng kết quả tối đa (mặc định 5)."
        }
    )

    async def run(self, query: str, limit: int = 5, user_id: str = None) -> ToolResult:
        return await self._do_search(query, "confluence", limit, user_id)


class JiraSearchTool(_BaseSearchTool):
    spec = ToolSpec(
        name="search_jira",
        description="Tìm kiếm task, issue, bug, ticket trong Jira.",
        parameters={
            "query": "Từ khóa tìm kiếm.",
            "limit": "Số lượng kết quả tối đa (mặc định 5)."
        }
    )

    async def run(self, query: str, limit: int = 5, user_id: str = None) -> ToolResult:
        return await self._do_search(query, "jira", limit, user_id)


class SlackSearchTool(_BaseSearchTool):
    spec = ToolSpec(
        name="search_slack",
        description="Tìm kiếm hội thoại, tin nhắn trong các kênh Slack.",
        parameters={
            "query": "Từ khóa tìm kiếm.",
            "limit": "Số lượng kết quả tối đa (mặc định 5)."
        }
    )

    async def run(self, query: str, limit: int = 5, user_id: str = None) -> ToolResult:
        return await self._do_search(query, "slack", limit, user_id)


class FileSearchTool(_BaseSearchTool):
    spec = ToolSpec(
        name="search_files",
        description="Tìm kiếm văn bản trong các file server (SMB/Shared Folders).",
        parameters={
            "query": "Từ khóa tìm kiếm.",
            "limit": "Số lượng kết quả tối đa (mặc định 5)."
        }
    )

    async def run(self, query: str, limit: int = 5, user_id: str = None) -> ToolResult:
        return await self._do_search(query, "file_server", limit, user_id)


class GlobalSearchTool(_BaseSearchTool):
    spec = ToolSpec(
        name="search_all",
        description="Tìm kiếm tổng hợp trên tất cả các nguồn dữ liệu.",
        parameters={
            "query": "Từ khóa tìm kiếm.",
            "limit": "Số lượng kết quả tối đa (mặc định 5)."
        }
    )

    async def run(self, query: str, limit: int = 5, user_id: str = None) -> ToolResult:
        return await self._do_search(query, "all", limit, user_id)
