from config.settings import settings
from orchestration.tools.base import BaseTool, ToolResult, ToolSpec

import httpx
import structlog


log = structlog.get_logger()


def _headers() -> dict[str, str] | None:
    if not settings.JIRA_API_TOKEN:
        return None
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
    }


class GetJiraIssueTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_jira_issue",
            description="Get one Jira issue by key.",
            parameters={
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Jira issue key"}},
                "required": ["key"],
            },
        )

    async def run(self, key: str, **_) -> ToolResult:
        headers = _headers()
        if not headers or not settings.JIRA_URL:
            return ToolResult(success=False, data={}, summary="", error="Jira is not configured")

        try:
            async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
                response = await client.get(
                    f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/issue/{key}",
                    headers=headers,
                )
            if response.status_code == 404:
                return ToolResult(success=False, data={}, summary="", error=f"Issue {key} does not exist")
            if response.status_code != 200:
                return ToolResult(success=False, data={}, summary="", error=f"Jira API error {response.status_code}")

            payload = response.json()
            fields = payload.get("fields", {})
            assignee = fields.get("assignee") or {}
            reporter = fields.get("reporter") or {}
            result = {
                "key": payload.get("key"),
                "summary": fields.get("summary", ""),
                "status": (fields.get("status") or {}).get("name", ""),
                "priority": (fields.get("priority") or {}).get("name", ""),
                "assignee": assignee.get("displayName", "Unassigned"),
                "reporter": reporter.get("displayName", ""),
                "description": (fields.get("description") or "")[:500],
                "created": fields.get("created", "")[:10],
                "updated": fields.get("updated", "")[:10],
                "labels": fields.get("labels", []),
                "url": f"{settings.JIRA_URL.rstrip('/')}/browse/{payload.get('key')}",
            }
            summary = (
                f"Issue {result['key']}: {result['summary']}\n"
                f"Status: {result['status']} | Priority: {result['priority']}\n"
                f"Assignee: {result['assignee']} | Reporter: {result['reporter']}\n"
                f"Description: {result['description']}\n"
                f"URL: {result['url']}"
            )
            return ToolResult(success=True, data=result, summary=summary)
        except Exception as exc:
            log.error("tool.get_jira_issue.error", key=key, error=str(exc))
            return ToolResult(success=False, data={}, summary="", error=str(exc))


class ListJiraIssuesTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_jira_issues",
            description="List Jira issues by JQL.",
            parameters={
                "type": "object",
                "properties": {
                    "jql": {"type": "string", "description": "JQL query"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10},
                },
                "required": ["jql"],
            },
        )

    async def run(self, jql: str, limit: int = 10, **_) -> ToolResult:
        headers = _headers()
        if not headers or not settings.JIRA_URL:
            return ToolResult(success=False, data=[], summary="", error="Jira is not configured")

        try:
            async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
                response = await client.post(
                    f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/search",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "jql": jql,
                        "maxResults": min(limit, 20),
                        "fields": ["summary", "status", "assignee", "priority", "created", "labels"],
                    },
                )
            if response.status_code == 400:
                return ToolResult(success=False, data=[], summary="", error="Invalid Jira JQL")
            if response.status_code != 200:
                return ToolResult(success=False, data=[], summary="", error=f"Jira API error {response.status_code}")

            issues = []
            for issue in response.json().get("issues", []):
                fields = issue.get("fields", {})
                issues.append(
                    {
                        "key": issue["key"],
                        "summary": fields.get("summary", ""),
                        "status": (fields.get("status") or {}).get("name", ""),
                        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                        "priority": (fields.get("priority") or {}).get("name", ""),
                        "url": f"{settings.JIRA_URL.rstrip('/')}/browse/{issue['key']}",
                    }
                )

            if not issues:
                return ToolResult(success=True, data=[], summary=f"No Jira issues for JQL: {jql}")
            return ToolResult(
                success=True,
                data=issues,
                summary="\n".join([f"Found {len(issues)} issues:"] + [f"- {item['key']}: {item['summary']}" for item in issues]),
            )
        except Exception as exc:
            log.error("tool.list_jira_issues.error", jql=jql, error=str(exc))
            return ToolResult(success=False, data=[], summary="", error=str(exc))
