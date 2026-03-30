from __future__ import annotations

import httpx
import structlog
from typing import Any

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
    extra_fields: dict[str, Any] | None = None,
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

    # 1. Filter extra_fields to keep ONLY what looks like a Jira custom field or known Jira field
    if extra_fields:
        internal_fields = {
            "channel_name", "channel_id", "thread_ts", "date", "evidence", "source_url",
            "source_type", "source_ref", "source_summary", "confidence", "evidence_list",
            "ts", "user", "text", "team", "blocks", "files", "parent_draft_id", "status",
            "id", "title", "description", "priority", "labels", "components", "due_date",
            "suggested_assignee", "jira_project", "issue_type"
        }
        # Be very strict: if we don't have createmeta, only allow customfield_
        filtered_extra = {
            k: v for k, v in extra_fields.items() 
            if k.startswith("customfield_") or (k not in internal_fields and k in {
                "environment", "security", "timetracking", "fixVersions", "versions"
            })
        }
        if filtered_extra:
            fields.update(filtered_extra)

    # 2. Fetch metadata to handle required fields or special fields like Epic Name
    # and to filter out any remaining invalid fields if we got a valid response.
    try:
        createmeta = await _get_create_fields(project, issue_type)
        if createmeta:
            # If we have createmeta, we can know exactly what's allowed.
            # Standard common Jira fields
            valid_keys = set(createmeta.keys()) | {
                "project", "summary", "description", "issuetype", "priority", 
                "labels", "components", "duedate", "assignee", "parent"
            }
            # Only keep fields that are actually defined in Jira
            fields = { k: v for k, v in fields.items() if k in valid_keys }
        
            # Handle Epic Name if missing
            if issue_type.lower() == "epic":
                epic_name_field_id = None
                for fid, fdef in createmeta.items():
                    name = str((fdef or {}).get("name") or "").strip().lower()
                    if name == "epic name":
                        epic_name_field_id = fid
                        break
                if epic_name_field_id and epic_name_field_id not in fields:
                    fields[epic_name_field_id] = title

            # Link to an epic when creating Story/Bug/Task (best-effort).
            if epic_key and issue_type.lower() != "epic":
                epic_link_field_id = None
                for fid, fdef in createmeta.items():
                    name = str((fdef or {}).get("name") or "").strip().lower()
                    if name == "epic link":
                        epic_link_field_id = fid
                        break
                if epic_link_field_id and epic_link_field_id not in fields:
                    fields[epic_link_field_id] = epic_key
                elif "parent" in createmeta and "parent" not in fields:
                    fields["parent"] = {"key": epic_key}

            # Handle other required fields (e.g., Severity)
            for fid, fdef in createmeta.items():
                if fdef.get("required") and fid not in fields:
                    name = str(fdef.get("name") or "").strip().lower()
                    if name == "severity":
                        allowed = fdef.get("allowedValues") or []
                        if allowed:
                            target = allowed[0]
                            for val in allowed:
                                vname = str(val.get("value") or val.get("name") or "").lower()
                                if "medium" in vname or "normal" in vname:
                                    target = val
                                    break
                            if "id" in target:
                                fields[fid] = {"id": target["id"]}
                            elif "value" in target:
                                fields[fid] = {"value": target["value"]}
                            else:
                                 fields[fid] = target
        else:
            # Fallback: if createmeta failed (like 404), we must be EXTREMELY conservative
            # to avoid 400 "Field cannot be set" errors.
            # We only keep standard fields and customfield_ ones.
            standard_fields = {
                "project", "summary", "description", "issuetype", "priority", 
                "labels", "components", "duedate", "assignee", "parent"
            }
            fields = {
                k: v for k, v in fields.items() 
                if k in standard_fields or k.startswith("customfield_")
            }
    except Exception as e:
        log.warning("jira_creator.createmeta_failed", error=str(e))

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
            
            # log full error for debugging
            log.error("jira_creator.failed", status=response.status_code, body=response.text[:500])
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
        # Clean up Slack-style mentions: remove @ and handle multiple mentions
        if "@" in query:
            # If multiple @, take the first one
            parts = [p.strip() for p in query.split("@") if p.strip()]
            if parts:
                query = parts[0]
        
        # Further clean up space-separated names if too long
        if len(query) > 50:
            query = query.split(" ")[0]

        if not query:
            return None

        async with httpx.AsyncClient(timeout=10, verify=settings.JIRA_VERIFY_TLS) as client:
            response = await client.get(
                f"{settings.JIRA_URL.rstrip('/')}/rest/api/2/user/search",
                params={"query": query, "maxResults": 3},
                headers=headers,
            )
            if response.status_code != 200:
                log.warning("jira_creator.assignee_search_failed", status=response.status_code, query=query)
                return None
            users = response.json()
            if not users:
                return None
            return users[0].get("accountId") or users[0].get("name")
    except Exception as e:
        log.warning("jira_creator.assignee_search_error", error=str(e))
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

    async def _fetch(path: str, use_params: bool = True) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
                p = params if use_params else {}
                resp = await client.get(f"{settings.JIRA_URL.rstrip('/')}{path}", headers=headers, params=p)
                if resp.status_code == 200:
                    return resp.json() if isinstance(resp.json(), dict) else {}
                log.warning("jira_creator.fetch_metadata_failed", path=path, status=resp.status_code)
                return {}
        except Exception as e:
            log.warning("jira_creator.fetch_metadata_error", path=path, error=str(e))
            return {}

    # Try different createmeta patterns
    # Pattern 1: Specific (most efficient if supported)
    data = await _fetch("/rest/api/2/issue/createmeta")
    
    # Pattern 2: Project-only (sometimes more reliable)
    if not data:
        old_names = params.pop("issuetypeNames", None)
        data = await _fetch("/rest/api/2/issue/createmeta")
        if old_names: params["issuetypeNames"] = old_names
        
    # Pattern 3: API v3 fallback
    if not data:
        data = await _fetch("/rest/api/3/issue/createmeta")

    fields: dict = {}
    try:
        projects = data.get("projects") or []
        if projects and isinstance(projects, list):
            # Try to match the exact project key
            project_data = next((p for p in projects if str(p.get("key")).lower() == project_key.lower()), projects[0])
            issuetypes = project_data.get("issuetypes") or []
            if issuetypes and isinstance(issuetypes, list):
                # Try to match the exact issue type name
                type_data = next((t for t in issuetypes if str(t.get("name")).lower() == issue_type.lower()), issuetypes[0])
                fields = type_data.get("fields") or {}
    except Exception as e:
        log.error("jira_creator.parse_metadata_failed", error=str(e))
        fields = {}

    # Hardcoded fallback for known required fields in this specific environment if meta fails
    if not fields and issue_type.lower() == "bug":
        # Based on logs, customfield_10120 is Severity
        fields["customfield_10120"] = {"name": "Severity", "required": True, "allowedValues": [{"value": "Medium", "id": "3"}]}

    _createmeta_cache[cache_key] = (now, fields or {})
    return fields or {}
