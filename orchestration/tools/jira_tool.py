"""
orchestration/tools/jira_tool.py

Tools:
- get_jira_issue
- list_jira_issues

Gọi trực tiếp Jira REST API (on-premise) bằng Personal Access Token (PAT).
"""

from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from config.settings import settings

import httpx
import structlog

log = structlog.get_logger()


# ==============================
# Global configuration
# ==============================

if not getattr(settings, "JIRA_API_TOKEN", None):
    raise RuntimeError("JIRA_API_TOKEN is not configured")

_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
}


# ==============================
# Tool: Get Jira Issue
# ==============================

class GetJiraIssueTool(BaseTool):

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_jira_issue",
            description=(
                "Lấy chi tiết một Jira issue theo key "
                "(ví dụ: ECOS-123 hoặc ECOS2025-45). "
                "Dùng khi user hỏi về một bug hoặc task cụ thể."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Jira issue key, ví dụ: ECOS-123 hoặc ECOS2025-45"
                    }
                },
                "required": ["key"]
            },
        )

    async def run(self, key: str, **_) -> ToolResult:

        url = f"{settings.JIRA_URL}/rest/api/2/issue/{key}"

        try:

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(url, headers=_HEADERS)

            # ===== error handling =====

            if resp.status_code == 401:
                return ToolResult(
                    success=False,
                    data={},
                    summary="",
                    error="Jira authentication failed (401)"
                )

            if resp.status_code == 404:
                return ToolResult(
                    success=False,
                    data={},
                    summary="",
                    error=f"Issue {key} không tồn tại"
                )

            if resp.status_code != 200:
                return ToolResult(
                    success=False,
                    data={},
                    summary="",
                    error=f"Jira API error {resp.status_code}: {resp.text}"
                )

            d = resp.json()

            fields = d.get("fields", {})
            assignee = fields.get("assignee") or {}
            reporter = fields.get("reporter") or {}

            result = {
                "key": d.get("key"),
                "summary": fields.get("summary", ""),
                "status": (fields.get("status") or {}).get("name", ""),
                "priority": (fields.get("priority") or {}).get("name", ""),
                "assignee": assignee.get("displayName", "Unassigned"),
                "reporter": reporter.get("displayName", ""),
                "description": (fields.get("description") or "")[:500],
                "created": fields.get("created", "")[:10],
                "updated": fields.get("updated", "")[:10],
                "labels": fields.get("labels", []),
                "url": f"{settings.JIRA_URL}/browse/{d.get('key')}",
            }

            summary = (
                f"Issue {result['key']}: {result['summary']}\n"
                f"Status: {result['status']} | Priority: {result['priority']}\n"
                f"Assignee: {result['assignee']} | Reporter: {result['reporter']}\n"
                f"Description: {result['description'][:200]}\n"
                f"URL: {result['url']}"
            )

            log.info("tool.get_jira_issue.success", key=key)

            return ToolResult(
                success=True,
                data=result,
                summary=summary
            )

        except Exception as e:

            log.error(
                "tool.get_jira_issue.error",
                key=key,
                error=str(e)
            )

            return ToolResult(
                success=False,
                data={},
                summary="",
                error=str(e)
            )


# ==============================
# Tool: List Jira Issues
# ==============================

class ListJiraIssuesTool(BaseTool):

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_jira_issues",
            description=(
                "Tìm danh sách Jira issues theo JQL. "
                "Dùng khi user hỏi về danh sách bug/task trong project hoặc sprint."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query, ví dụ: project=ECOS2025 AND status=Open"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Số lượng tối đa issues trả về",
                        "default": 10
                    }
                },
                "required": ["jql"]
            },
        )

    async def run(self, jql: str, limit: int = 10, **_) -> ToolResult:

        url = f"{settings.JIRA_URL}/rest/api/2/search"

        body = {
            "jql": jql,
            "maxResults": min(limit, 20),
            "fields": [
                "summary",
                "status",
                "assignee",
                "priority",
                "created",
                "labels"
            ],
        }

        headers = {
            **_HEADERS,
            "Content-Type": "application/json"
        }

        try:

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.post(url, headers=headers, json=body)

            # ===== error handling =====

            if resp.status_code == 401:
                return ToolResult(
                    success=False,
                    data=[],
                    summary="",
                    error="Jira authentication failed (401)"
                )

            if resp.status_code == 400:
                err = resp.json().get("errorMessages", [resp.text])
                return ToolResult(
                    success=False,
                    data=[],
                    summary="",
                    error=f"Jira JQL error: {err}"
                )

            if resp.status_code != 200:
                return ToolResult(
                    success=False,
                    data=[],
                    summary="",
                    error=f"Jira API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()

            issues = []

            for issue in data.get("issues", []):
                f = issue.get("fields", {})

                assignee = (f.get("assignee") or {}).get(
                    "displayName",
                    "Unassigned"
                )

                issues.append({
                    "key": issue["key"],
                    "summary": f.get("summary", ""),
                    "status": (f.get("status") or {}).get("name", ""),
                    "assignee": assignee,
                    "priority": (f.get("priority") or {}).get("name", ""),
                    "url": f"{settings.JIRA_URL}/browse/{issue['key']}",
                })

            if not issues:

                return ToolResult(
                    success=True,
                    data=[],
                    summary=f"Không tìm thấy issue nào với JQL: {jql}"
                )

            lines = [
                f"Tìm thấy {len(issues)} issues (JQL: {jql}):"
            ]

            for i in issues:
                lines.append(
                    f"- {i['key']}: {i['summary']} "
                    f"[{i['status']}] → {i['assignee']}"
                )

            log.info(
                "tool.list_jira_issues.success",
                jql=jql,
                found=len(issues)
            )

            return ToolResult(
                success=True,
                data=issues,
                summary="\n".join(lines)
            )

        except Exception as e:

            log.error(
                "tool.list_jira_issues.error",
                jql=jql,
                error=str(e)
            )

            return ToolResult(
                success=False,
                data=[],
                summary="",
                error=str(e)
            )