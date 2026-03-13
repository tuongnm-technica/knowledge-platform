"""
orchestration/tools/confluence_tool.py

Tools:
- search_confluence
- get_confluence_page

Gọi trực tiếp Confluence REST API (on-premise / cloud).
"""

from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from config.settings import settings

import httpx
import structlog

log = structlog.get_logger()


# ==========================
# Config
# ==========================

if not getattr(settings, "CONFLUENCE_API_TOKEN", None):
    raise RuntimeError("CONFLUENCE_API_TOKEN not configured")

_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {settings.CONFLUENCE_API_TOKEN}",
}


# ==========================
# Tool: Search Confluence
# ==========================

class SearchConfluenceTool(BaseTool):

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_confluence",
            description=(
                "Tìm kiếm tài liệu trong Confluence theo keyword. "
                "Dùng khi user hỏi về tài liệu kỹ thuật, API spec, design document."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Từ khóa tìm kiếm"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Số kết quả tối đa",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        )

    async def run(self, query: str, limit: int = 5, **_) -> ToolResult:

        url = f"{settings.CONFLUENCE_URL}/rest/api/search"

        params = {
            "cql": f'text ~ "{query}"',
            "limit": min(limit, 10),
        }

        try:

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(url, headers=_HEADERS, params=params)

            if resp.status_code == 401:
                return ToolResult(
                    success=False,
                    data=[],
                    summary="",
                    error="Confluence authentication failed (401)"
                )

            if resp.status_code != 200:
                return ToolResult(
                    success=False,
                    data=[],
                    summary="",
                    error=f"Confluence API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()

            results = []

            for r in data.get("results", []):
                content = r.get("content", {})
                title = content.get("title", "")
                page_id = content.get("id")

                results.append({
                    "id": page_id,
                    "title": title,
                    "url": f"{settings.CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
                })

            if not results:
                return ToolResult(
                    success=True,
                    data=[],
                    summary=f"Không tìm thấy tài liệu nào cho '{query}'"
                )

            lines = [f"Tìm thấy {len(results)} tài liệu:"]
            for r in results:
                lines.append(f"- {r['title']}")

            log.info(
                "tool.search_confluence.success",
                query=query,
                found=len(results)
            )

            return ToolResult(
                success=True,
                data=results,
                summary="\n".join(lines)
            )

        except Exception as e:

            log.error(
                "tool.search_confluence.error",
                query=query,
                error=str(e)
            )

            return ToolResult(
                success=False,
                data=[],
                summary="",
                error=str(e)
            )


# ==========================
# Tool: Get Confluence Page
# ==========================

class GetConfluencePageTool(BaseTool):

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_confluence_page",
            description=(
                "Lấy nội dung chi tiết của một trang Confluence theo page ID."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Confluence page id"
                    }
                },
                "required": ["page_id"]
            }
        )

    async def run(self, page_id: str, **_) -> ToolResult:

        url = f"{settings.CONFLUENCE_URL}/rest/api/content/{page_id}"

        params = {
            "expand": "body.storage,version"
        }

        try:

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(url, headers=_HEADERS, params=params)

            if resp.status_code == 401:
                return ToolResult(
                    success=False,
                    data={},
                    summary="",
                    error="Confluence authentication failed (401)"
                )

            if resp.status_code != 200:
                return ToolResult(
                    success=False,
                    data={},
                    summary="",
                    error=f"Confluence API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()

            title = data.get("title", "")

            body = (
                data.get("body", {})
                .get("storage", {})
                .get("value", "")
            )

            body = body[:2000]

            result = {
                "title": title,
                "content": body,
                "url": f"{settings.CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
            }

            summary = f"{title}\n\n{body[:3000]}..."

            log.info(
                "tool.get_confluence_page.success",
                page_id=page_id
            )

            return ToolResult(
                success=True,
                data=result,
                summary=summary
            )

        except Exception as e:

            log.error(
                "tool.get_confluence_page.error",
                page_id=page_id,
                error=str(e)
            )

            return ToolResult(
                success=False,
                data={},
                summary="",
                error=str(e)
            )