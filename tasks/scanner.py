"""
tasks/scanner.py
Quét Slack messages + Confluence pages gần đây → extract action items → lưu drafts.
Được gọi bởi: scheduler (tự động đêm) và API endpoint (manual trigger).
"""
from __future__ import annotations
import httpx
import structlog
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from tasks.extractor import extract_tasks_from_content
from tasks.repository import TaskDraftRepository
from config.settings import settings

log = structlog.get_logger()


async def scan_and_create_drafts(
    session:     AsyncSession,
    triggered_by: str = "scheduler",
    created_by:   str | None = None,
    slack_days:   int = 1,          # quét bao nhiêu ngày Slack
    confluence_days: int = 1,       # quét Confluence pages edited trong N ngày
) -> dict:
    """
    Main entry point — quét cả Slack lẫn Confluence, tạo drafts.
    Trả về stats: {slack_tasks, confluence_tasks, total}
    """
    repo = TaskDraftRepository(session)
    stats = {"slack_tasks": 0, "confluence_tasks": 0, "total": 0, "errors": []}

    # ── Slack scan ──
    try:
        slack_count = await _scan_slack(
            repo, triggered_by, created_by, days_back=slack_days
        )
        stats["slack_tasks"] = slack_count
    except Exception as e:
        log.error("scanner.slack.error", error=str(e))
        stats["errors"].append(f"Slack: {str(e)}")

    # ── Confluence scan ──
    try:
        conf_count = await _scan_confluence(
            repo, triggered_by, created_by, days_back=confluence_days
        )
        stats["confluence_tasks"] = conf_count
    except Exception as e:
        log.error("scanner.confluence.error", error=str(e))
        stats["errors"].append(f"Confluence: {str(e)}")

    stats["total"] = stats["slack_tasks"] + stats["confluence_tasks"]
    log.info("scanner.done", **{k: v for k, v in stats.items() if k != "errors"})
    return stats


# ─── Slack ────────────────────────────────────────────────────────────────────

# Cache user ID → display name trong 1 scan session
_user_cache: dict[str, str] = {}


async def _resolve_slack_users(text: str, headers: dict) -> str:
    """Thay @U074K06KZD1 → tên thật từ Slack API."""
    import re
    user_ids = re.findall(r"@(U[A-Z0-9]+)", text)
    if not user_ids:
        return text

    async with httpx.AsyncClient(timeout=10) as client:
        for uid in set(user_ids):
            if uid not in _user_cache:
                try:
                    r = await client.get(
                        "https://slack.com/api/users.info",
                        headers=headers,
                        params={"user": uid},
                    )
                    d = r.json()
                    if d.get("ok"):
                        _user_cache[uid] = d["user"].get("real_name") or d["user"].get("name", uid)
                    else:
                        _user_cache[uid] = uid
                except Exception:
                    _user_cache[uid] = uid

    result = text
    for uid, name in _user_cache.items():
        result = result.replace(f"@{uid}", f"@{name}")
    return result


async def _scan_slack(
    repo: TaskDraftRepository,
    triggered_by: str,
    created_by: str | None,
    days_back: int = 1,
) -> int:
    """Quét tất cả public channels → extract tasks → lưu drafts."""
    if not settings.SLACK_BOT_TOKEN:
        log.warning("scanner.slack.no_token")
        return 0

    headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
    channels = await _get_slack_channels(headers)
    total = 0

    for ch in channels:
        ch_id   = ch["id"]
        ch_name = ch.get("name", ch_id)
        content = await _get_channel_messages(headers, ch_id, days_back)
        if not content:
            continue

        tasks = await extract_tasks_from_content(
            content=content,
            source_type="slack",
            source_ref=f"#{ch_name}",
        )

        # Resolve Slack user IDs trong assignee
        for task in tasks:
            if task.suggested_assignee:
                task.suggested_assignee = await _resolve_slack_users(
                    task.suggested_assignee, headers
                )
            draft_id = await repo.create_draft(
                title=task.title,
                description=task.description,
                source_type="slack",
                source_ref=f"#{ch_name}",
                source_summary=content[:300],
                suggested_assignee=task.suggested_assignee,
                priority=task.priority,
                labels=task.labels,
                triggered_by=triggered_by,
                created_by=created_by,
            )
            if draft_id:  # None = duplicate, skip
                total += 1

    return total


async def _get_slack_channels(headers: dict) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://slack.com/api/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": 100},
            )
            data = resp.json()
            return [c for c in data.get("channels", []) if not c.get("is_archived")]
    except Exception as e:
        log.error("scanner.slack.list_channels", error=str(e))
        return []


async def _get_channel_messages(headers: dict, channel_id: str, days_back: int) -> str:
    oldest = (datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://slack.com/api/conversations.history",
                headers=headers,
                params={"channel": channel_id, "oldest": str(oldest), "limit": 100},
            )
            data = resp.json()
            msgs = [
                m.get("text", "") for m in data.get("messages", [])
                if m.get("type") == "message" and m.get("text")
            ]
            return "\n".join(msgs)
    except Exception:
        return ""


# ─── Confluence ───────────────────────────────────────────────────────────────

async def _scan_confluence(
    repo: TaskDraftRepository,
    triggered_by: str,
    created_by: str | None,
    days_back: int = 1,
) -> int:
    """Quét Confluence pages được edit trong N ngày → extract tasks."""
    if not settings.CONFLUENCE_URL or not settings.CONFLUENCE_API_TOKEN:
        log.warning("scanner.confluence.no_config")
        return 0

    auth    = (settings.CONFLUENCE_USERNAME or "", settings.CONFLUENCE_API_TOKEN)
    since   = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    total   = 0

    try:
        pages = await _get_recent_confluence_pages(auth, since)
    except Exception as e:
        log.error("scanner.confluence.fetch", error=str(e))
        return 0

    for page in pages:
        page_id    = page.get("id", "")
        page_title = page.get("title", "")
        content    = page.get("body", {}).get("storage", {}).get("value", "")

        # Strip HTML tags đơn giản
        import re
        clean = re.sub(r"<[^>]+>", " ", content).strip()
        if len(clean) < 100:
            continue

        tasks = await extract_tasks_from_content(
            content=clean,
            source_type="confluence",
            source_ref=page_id,
        )

        for task in tasks:
            await repo.create_draft(
                title=task.title,
                description=task.description,
                source_type="confluence",
                source_ref=page_id,
                source_summary=f"[{page_title}] {clean[:300]}",
                suggested_assignee=task.suggested_assignee,
                priority=task.priority,
                labels=task.labels,
                triggered_by=triggered_by,
                created_by=created_by,
            )
            total += 1

    return total


async def _get_recent_confluence_pages(auth: tuple, since: str) -> list[dict]:
    """Lấy pages được edit sau `since` date."""
    url    = f"{settings.CONFLUENCE_URL}/rest/api/content"
    params = {
        "type":       "page",
        "expand":     "body.storage",
        "limit":      20,
        "orderby":    "modified desc",
        "spaceKey":   "EEP2",
    }
    try:
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.get(url, params=params, auth=auth)
            resp.raise_for_status()
            return resp.json().get("results", [])
    except Exception as e:
        log.error("scanner.confluence.api", error=str(e))
        return []