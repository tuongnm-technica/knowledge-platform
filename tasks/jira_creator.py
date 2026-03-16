from __future__ import annotations

import httpx
import structlog

from config.settings import settings


log = structlog.get_logger()

PRIORITY_MAP = {
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}


async def submit_to_jira(
    project: str,
    title: str,
    description: str,
    assignee: str | None = None,
    priority: str = "Medium",
    labels: list[str] | None = None,
    components: list[str] | None = None,
    due_date: str | object | None = None,
    issue_type: str = "Task",
    epic_key: str | None = None,
 ) -> dict | None:
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        log.error("jira_creator.no_config")
        return None

    issue_type = (issue_type or "Task").strip() or "Task"

    fields: dict[str, object] = {
        "project": {"key": project},
        "summary": title,
        "description": description or title,
        "issuetype": {"name": issue_type},
        "priority": {"name": PRIORITY_MAP.get(priority, "Medium")},
    }
    if labels:
        fields["labels"] = labels

    if components:
        fields["components"] = [{"name": c} for c in components if c and str(c).strip()]

    if due_date:
        # Jira expects YYYY-MM-DD string in "duedate".
        try:
            if hasattr(due_date, "isoformat"):
                due_date = due_date.isoformat()  # type: ignore[assignment]
        except Exception:
            pass
        due_str = str(due_date).strip()
        if due_str:
            fields["duedate"] = due_str

    # Jira Epic-specific required field discovery (best-effort, no hardcoded customfield ids).
    # Some Jira instances require "Epic Name" custom field for Epic issuetype.
    if issue_type.lower() == "epic":
        try:
            create_fields = await _get_create_fields(project, issue_type)
            epic_name_field_id = None
            for fid, fdef in create_fields.items():
                name = str((fdef or {}).get("name") or "").strip().lower()
                if name == "epic name":
                    epic_name_field_id = fid
                    break
            if epic_name_field_id and epic_name_field_id not in fields:
                fields[epic_name_field_id] = title
        except Exception:
            pass

    # Link to an epic when creating Story/Bug/Task (best-effort).
    if epic_key and issue_type.lower() != "epic":
        try:
            create_fields = await _get_create_fields(project, issue_type)
            epic_link_field_id = None
            for fid, fdef in create_fields.items():
                name = str((fdef or {}).get("name") or "").strip().lower()
                if name == "epic link":
                    epic_link_field_id = fid
                    break
            if epic_link_field_id:
                fields[epic_link_field_id] = epic_key
            elif "parent" in create_fields:
                # Jira Cloud next-gen often uses parent to attach hierarchy.
                fields["parent"] = {"key": epic_key}
        except Exception:
            pass

    resolved_account_id: str | None = None

    if assignee:
        account_id = await _resolve_assignee(assignee)
        if account_id:
            resolved_account_id = account_id
            fields["assignee"] = {"accountId": account_id}
        else:
            fields["description"] = f"{fields['description']}\n\nSuggested assignee: {assignee}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
    }

    try:
        async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
            response = await client.post(
                f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/issue",
                headers=headers,
                json={"fields": fields},
            )
            if response.status_code in (200, 201):
                key = response.json().get("key")
                log.info("jira_creator.success", key=key, title=title[:50])
                return {"key": key, "assignee_account_id": resolved_account_id, "issue_type": issue_type}
            log.error("jira_creator.failed", status=response.status_code, body=response.text[:200])
            return None
    except Exception as exc:
        log.error("jira_creator.error", error=str(exc))
        return None


async def _resolve_assignee(display_name: str) -> str | None:
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {settings.JIRA_API_TOKEN}"}
    try:
        query = display_name.strip()
        if "@" in query and query.count("@") == 1:
            # Prefer email-based mapping when available.
            query = query
        async with httpx.AsyncClient(timeout=10, verify=settings.JIRA_VERIFY_TLS) as client:
            response = await client.get(
                f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/user/search",
                params={"query": query, "maxResults": 3},
                headers=headers,
            )
            if response.status_code != 200:
                return None
            users = response.json()
            if not users:
                return None
            return users[0].get("accountId") or users[0].get("name")
    except Exception:
        return None


_createmeta_cache: dict[str, tuple[float, dict]] = {}


async def _get_create_fields(project_key: str, issue_type: str) -> dict:
    """
    Fetch Jira create metadata fields for (project, issuetype).
    Uses /rest/api/2/issue/createmeta (fallback /rest/api/3) and caches briefly in-memory.
    """
    import time

    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        return {}

    cache_key = f"{project_key}::{issue_type}".lower()
    now = time.time()
    cached = _createmeta_cache.get(cache_key)
    if cached and (now - cached[0]) < 3600:
        return cached[1] or {}

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
    }
    params = {
        "projectKeys": project_key,
        "issuetypeNames": issue_type,
        "expand": "projects.issuetypes.fields",
    }

    async def _fetch(path: str) -> dict:
        async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
            resp = await client.get(f"{settings.JIRA_URL.rstrip('/')}{path}", headers=headers, params=params)
            if resp.status_code != 200:
                return {}
            return resp.json() if isinstance(resp.json(), dict) else {}

    data = await _fetch("/rest/api/2/issue/createmeta")
    if not data:
        data = await _fetch("/rest/api/3/issue/createmeta")

    fields: dict = {}
    try:
        projects = data.get("projects") or []
        if projects and isinstance(projects, list):
            issuetypes = (projects[0] or {}).get("issuetypes") or []
            if issuetypes and isinstance(issuetypes, list):
                fields = (issuetypes[0] or {}).get("fields") or {}
    except Exception:
        fields = {}

    _createmeta_cache[cache_key] = (now, fields or {})
    return fields or {}
