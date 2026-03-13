"""
tasks/jira_creator.py
Submit confirmed draft task lên Jira thật.
"""
from __future__ import annotations
import httpx
import structlog
from config.settings import settings

log = structlog.get_logger()

PRIORITY_MAP = {
    "High":   "High",
    "Medium": "Medium",
    "Low":    "Low",
}


async def submit_to_jira(
    project:    str,
    title:      str,
    description: str,
    assignee:   str | None = None,
    priority:   str = "Medium",
    labels:     list[str] | None = None,
) -> str | None:
    """
    Tạo Jira issue thật.
    Trả về issue key (vd: ECOS2025-123) hoặc None nếu lỗi.
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        log.error("jira_creator.no_config")
        return None

    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN) if settings.JIRA_USERNAME else None

    # Build issue body
    fields: dict = {
        "project":     {"key": project},
        "summary":     title,
        "description": description or title,
        "issuetype":   {"name": "Task"},
        "priority":    {"name": PRIORITY_MAP.get(priority, "Medium")},
    }

    if labels:
        fields["labels"] = labels

    # Assignee: Jira on-premise dùng accountId hoặc name
    if assignee:
        # Thử resolve assignee theo display name
        account_id = await _resolve_assignee(assignee)
        if account_id:
            fields["assignee"] = {"accountId": account_id}
        else:
            # Fallback: ghi vào description
            fields["description"] += f"\n\nAssignee gợi ý: {assignee}"

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.post(
                f"{settings.JIRA_URL}/rest/api/2/issue",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={"fields": fields},
                auth=auth,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                key  = data.get("key")
                log.info("jira_creator.success", key=key, title=title[:50])
                return key
            else:
                log.error("jira_creator.failed", status=resp.status_code, body=resp.text[:200])
                return None
    except Exception as e:
        log.error("jira_creator.error", error=str(e))
        return None


async def _resolve_assignee(display_name: str) -> str | None:
    """Tìm Jira accountId từ display name."""
    if not settings.JIRA_URL:
        return None
    auth = (settings.JIRA_USERNAME, settings.JIRA_API_TOKEN) if settings.JIRA_USERNAME else None
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(
                f"{settings.JIRA_URL}/rest/api/2/user/search",
                params={"query": display_name, "maxResults": 3},
                auth=auth,
            )
            if resp.status_code == 200:
                users = resp.json()
                if users:
                    return users[0].get("accountId") or users[0].get("name")
    except Exception:
        pass
    return None