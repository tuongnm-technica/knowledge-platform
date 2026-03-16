from config.settings import settings
from orchestration.tools.base import BaseTool, ToolResult, ToolSpec

import httpx
import structlog


log = structlog.get_logger()


def _headers() -> dict[str, str] | None:
    if not settings.CONFLUENCE_API_TOKEN:
        return None
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.CONFLUENCE_API_TOKEN}",
    }


class SearchConfluenceTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_confluence",
            description="Search Confluence documents by keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 5},
                },
                "required": ["query"],
            },
        )

    async def run(self, query: str, limit: int = 5, **_) -> ToolResult:
        headers = _headers()
        if not headers or not settings.CONFLUENCE_URL:
            return ToolResult(success=False, data=[], summary="", error="Confluence is not configured")

        try:
            async with httpx.AsyncClient(timeout=15, verify=settings.CONFLUENCE_VERIFY_TLS) as client:
                response = await client.get(
                    f"{settings.CONFLUENCE_URL.rstrip('/')}/rest/api/search",
                    headers=headers,
                    params={"cql": f'text ~ "{query}"', "limit": min(limit, 10)},
                )
            if response.status_code != 200:
                return ToolResult(success=False, data=[], summary="", error=f"Confluence API error {response.status_code}")

            results = []
            for item in response.json().get("results", []):
                content = item.get("content", {})
                page_id = content.get("id")
                results.append(
                    {
                        "id": page_id,
                        "title": content.get("title", ""),
                        "url": f"{settings.CONFLUENCE_URL.rstrip('/')}/pages/viewpage.action?pageId={page_id}",
                    }
                )

            if not results:
                return ToolResult(success=True, data=[], summary=f"No Confluence results for '{query}'")
            return ToolResult(
                success=True,
                data=results,
                summary="\n".join([f"Found {len(results)} documents:"] + [f"- {item['title']}" for item in results]),
            )
        except Exception as exc:
            log.error("tool.search_confluence.error", query=query, error=str(exc))
            return ToolResult(success=False, data=[], summary="", error=str(exc))


class GetConfluencePageTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_confluence_page",
            description="Get one Confluence page by page id.",
            parameters={
                "type": "object",
                "properties": {"page_id": {"type": "string", "description": "Confluence page id"}},
                "required": ["page_id"],
            },
        )

    async def run(self, page_id: str, **_) -> ToolResult:
        headers = _headers()
        if not headers or not settings.CONFLUENCE_URL:
            return ToolResult(success=False, data={}, summary="", error="Confluence is not configured")

        try:
            async with httpx.AsyncClient(timeout=15, verify=settings.CONFLUENCE_VERIFY_TLS) as client:
                response = await client.get(
                    f"{settings.CONFLUENCE_URL.rstrip('/')}/rest/api/content/{page_id}",
                    headers=headers,
                    params={"expand": "body.storage,version"},
                )
            if response.status_code != 200:
                return ToolResult(success=False, data={}, summary="", error=f"Confluence API error {response.status_code}")

            payload = response.json()
            body = payload.get("body", {}).get("storage", {}).get("value", "")[:2000]
            result = {
                "title": payload.get("title", ""),
                "content": body,
                "url": f"{settings.CONFLUENCE_URL.rstrip('/')}/pages/viewpage.action?pageId={page_id}",
            }
            return ToolResult(success=True, data=result, summary=f"{result['title']}\n\n{body[:3000]}...")
        except Exception as exc:
            log.error("tool.get_confluence_page.error", page_id=page_id, error=str(exc))
            return ToolResult(success=False, data={}, summary="", error=str(exc))
