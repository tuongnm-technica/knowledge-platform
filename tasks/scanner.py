from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import asyncio

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from connectors.confluence.confluence_client import ConfluenceClient
from connectors.confluence.confluence_parser import ConfluenceParser
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from tasks.extractor import extract_tasks_from_content
from tasks.repository import TaskDraftRepository
from utils.vision import describe_images_batch


log = structlog.get_logger()
_user_cache: dict[str, str] = {}
_epic_re = re.compile(r"\b([A-Z][A-Z0-9]{1,10}-\d+)\b")


async def _load_connector_selection(session: AsyncSession, connector: str) -> dict:
    try:
        result = await session.execute(
            text("SELECT selection FROM connector_configs WHERE connector = :c"),
            {"c": connector},
        )
        raw = result.scalar()
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw) if raw else {}
    except Exception:
        return {}

    # Multi-instance (new): fall back to the first instance config for this connector type.
    try:
        inst = await session.execute(
            text(
                """
                SELECT id::text
                FROM connector_instances
                WHERE connector_type = :t
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"t": connector},
        )
        instance_id = inst.scalar()
        if instance_id:
            connector_key = f"{connector}:{instance_id}"
            result = await session.execute(
                text("SELECT selection FROM connector_configs WHERE connector = :c"),
                {"c": connector_key},
            )
            raw = result.scalar()
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                return json.loads(raw) if raw else {}
    except Exception:
        return {}
    return {}


def _csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _slack_deep_link(channel_id: str, ts: str) -> str:
    ts = str(ts or "").strip()
    if not ts:
        return f"https://slack.com/archives/{channel_id}"
    if "." in ts:
        sec, frac = ts.split(".", 1)
        frac = (frac + "000000")[:6]
        ts_digits = f"{sec}{frac}"
    else:
        ts_digits = "".join([c for c in ts if c.isdigit()])
    return f"https://slack.com/archives/{channel_id}/p{ts_digits}"


def _detect_epic_key(text: str) -> str | None:
    """
    Best-effort: if the content explicitly mentions "epic" and contains a Jira-like key,
    use that as epic_key for grouping/linking.
    """
    text = str(text or "")
    if not text:
        return None
    if "epic" not in text.lower():
        return None
    m = _epic_re.search(text)
    return m.group(1) if m else None

def _suggest_issue_type_from_labels(labels: list[str] | None) -> str:
    """Basic issue type suggestion from labels (can be overridden by LLM)."""
    lower_labels = {str(x).lower() for x in (labels or [])}
    if "bug" in lower_labels:
        return "Bug"
    if "feature" in lower_labels:
        return "Story"
    return "Task"


async def scan_and_create_drafts(
    session: AsyncSession,
    triggered_by: str = "scheduler",
    created_by: str | None = None,
    slack_days: int = 1,
    confluence_days: int = 1,
) -> dict:
    repo = TaskDraftRepository(session)
    stats = {"slack_tasks": 0, "confluence_tasks": 0, "total": 0, "errors": []}
    async with httpx.AsyncClient(timeout=30) as http_client:
        try:
            stats["slack_tasks"] = await _scan_slack(session, repo, triggered_by, created_by, http_client, days_back=slack_days)
        except Exception as exc:
            log.error("scanner.slack.error", error=str(exc))
            stats["errors"].append(f"Slack: {exc}")

        try:
            stats["confluence_tasks"] = await _scan_confluence(session, repo, triggered_by, created_by, http_client, days_back=confluence_days)
        except Exception as exc:
            log.error("scanner.confluence.error", error=str(exc))
            stats["errors"].append(f"Confluence: {exc}")

    stats["total"] = stats["slack_tasks"] + stats["confluence_tasks"]
    log.info("scanner.done", **{key: value for key, value in stats.items() if key != "errors"})
    return stats


async def _resolve_slack_users(text: str, client: httpx.AsyncClient, headers: dict) -> str:
    user_ids = re.findall(r"@(U[A-Z0-9]+)", text)
    if not user_ids:
        return text

    async with httpx.AsyncClient(timeout=10) as client:
        for user_id in set(user_ids):
            if user_id in _user_cache:
                continue
            try:
                response = await client.get(
                    "https://slack.com/api/users.info",
                    headers=headers,
                    params={"user": user_id},
                )
                payload = response.json()
                if payload.get("ok"):
                    user = payload["user"]
                    _user_cache[user_id] = user.get("real_name") or user.get("name", user_id)
                else:
                    _user_cache[user_id] = user_id
            except Exception:
                _user_cache[user_id] = user_id

    result = text
    for user_id, name in _user_cache.items():
        result = result.replace(f"@{user_id}", f"@{name}")
    return result


async def _scan_slack(
    session: AsyncSession,
    repo: TaskDraftRepository,
    triggered_by: str,
    created_by: str | None,
    http_client: httpx.AsyncClient,
    days_back: int = 1,
) -> int:
    if not settings.SLACK_BOT_TOKEN:
        log.warning("scanner.slack.no_token")
        return 0

    selection = await _load_connector_selection(session, "slack")
    selected_channels = set([str(x) for x in (selection.get("channels") or [])]) if isinstance(selection, dict) else set()

    client = SlackClient()
    parser = SlackParser()
    user_cache = client.get_user_cache()
    total = 0

    channels = await client.get_channels()
    if selected_channels:
        channels = [c for c in channels if str(c.get("id") or "") in selected_channels]

    headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}

    for channel in channels:
        channel_id = channel["id"]
        channel_name = channel.get("name", channel_id)

        messages = await client.get_messages(channel_id, days=days_back)
        if not messages:
            continue

        # Group messages by date so we can keep links stable and content bounded.
        by_date: dict[str, list[dict]] = defaultdict(list)
        for msg in messages:
            try:
                ts = float(msg.get("ts", 0))
            except Exception:
                ts = 0.0
            if not ts:
                continue
            date_key = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            by_date[date_key].append(msg)

        for date_key, msgs in sorted(by_date.items(), key=lambda x: x[0], reverse=True):
            msgs.sort(key=lambda m: float(m.get("ts", 0) or 0))

            content = parser.extract_thread_content(
                msgs,
                user_cache=user_cache,
                channel_name=channel_name,
                date_str=date_key,
            )
            if not content or len(content.strip()) < 50:
                continue

            # Best-effort stable deep link to the first indexable message in this chunk/day.
            first_ts = None
            for msg in msgs:
                if msg.get("subtype") in (
                    "bot_message",
                    "channel_join",
                    "channel_leave",
                    "channel_archive",
                    "channel_unarchive",
                ):
                    continue
                ts_raw = str(msg.get("ts") or "").strip()
                if ts_raw and (str(msg.get("text") or "").strip() or msg.get("attachments")):
                    first_ts = ts_raw
                    break

            base_url = _slack_deep_link(channel_id, first_ts) if first_ts else _slack_deep_link(channel_id, "")

            tasks = await extract_tasks_from_content(
                content=content,
                source_type="slack",
                client=http_client,
                source_ref=f"#{channel_name} | {date_key}",
            )

            for task in tasks:
                suggested_assignee = task.suggested_assignee
                if suggested_assignee:
                    suggested_assignee = await _resolve_slack_users(suggested_assignee, http_client, headers)
                else:
                    # Smart assignee suggestion (MVP): use history based on labels.
                    suggested_assignee = await repo.suggest_assignee_from_history(labels=task.labels or [])

                evidence_ts = (task.evidence_ts or "").strip()
                source_url = _slack_deep_link(channel_id, evidence_ts) if evidence_ts else base_url

                quote = (task.evidence or "").strip()
                if not quote and evidence_ts and content:
                    # Try to extract the exact Slack line that contains the ts marker.
                    needle = f"|{evidence_ts}]"
                    for line in content.splitlines():
                        if needle in line:
                            quote = line.strip()
                            break

                # Basic issue type suggestion from labels (LLM can still propose via content, but we start safe).
                issue_type = _suggest_issue_type_from_labels(task.labels)
                epic_key = _detect_epic_key(f"{task.title}\n{task.description}")

                draft_id = await repo.create_draft(
                    title=task.title,
                    description=task.description,
                    source_type="slack",
                    source_ref=f"#{channel_name} | {date_key}",
                    source_summary=content[:300],
                    source_url=source_url,
                    scope_group_id=f"group_slack_channel_{str(channel_id or '').strip().lower()}",
                    source_meta={
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "date": date_key,
                        "evidence_ts": evidence_ts,
                        "evidence": quote,
                    },
                    evidence=[
                        {
                            "source": "slack",
                            "url": source_url,
                            "quote": quote or content[:300],
                            "ref": {"channel_id": channel_id, "ts": evidence_ts},
                        }
                    ],
                    issue_type=issue_type,
                    epic_key=epic_key,
                    suggested_assignee=suggested_assignee,
                    priority=task.priority,
                    labels=task.labels,
                    triggered_by=triggered_by,
                    created_by=created_by,
                )
                if draft_id:
                    total += 1

    return total


async def _scan_confluence(
    session: AsyncSession,
    repo: TaskDraftRepository,
    triggered_by: str,
    created_by: str | None,
    http_client: httpx.AsyncClient,
    days_back: int = 1,
) -> int:
    if not settings.CONFLUENCE_URL or not settings.CONFLUENCE_API_TOKEN:
        log.warning("scanner.confluence.no_config")
        return 0

    total = 0

    selection = await _load_connector_selection(session, "confluence")
    selected_spaces = set([str(x) for x in (selection.get("spaces") or [])]) if isinstance(selection, dict) else set()

    conf_client = ConfluenceClient()
    parser = ConfluenceParser()

    since_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    configured_spaces = selected_spaces or set(_csv_values(settings.CONFLUENCE_SPACE_KEYS))

    # If no spaces configured, scan all accessible spaces (client lists spaces and filters pages by CQL per space).
    spaces = conf_client.get_spaces()
    space_keys = [s.get("key") for s in spaces if s.get("key")]
    if configured_spaces:
        space_keys = [k for k in space_keys if k in configured_spaces]

    for space_key in space_keys:
        pages = await asyncio.to_thread(conf_client.get_pages_since, space_key, since_dt, 200)
        for page in pages:
            page_id = str(page.get("id") or "").strip()
            if not page_id:
                continue

            page_title = str(page.get("title") or "").strip()
            body_html = await asyncio.to_thread(conf_client.get_page_body, page_id)
            clean = parser.parse(body_html)

            if not clean or len(clean.strip()) < 120:
                continue

            # Vision enhancement (MVP): caption referenced images so extractor can create better tasks.
            if settings.VISION_ENABLED and str(settings.OLLAMA_VISION_MODEL or "").strip():
                try:
                    import re

                    wanted = re.findall(r"\[\[IMAGE:([^\]]+)\]\]", clean or "")
                    wanted = [str(x or "").strip() for x in wanted if str(x or "").strip()]
                    wanted = list(dict.fromkeys(wanted))[:2]
                    if wanted:
                        atts = await asyncio.to_thread(conf_client.list_attachments, page_id, 200)
                        by_name = {str(a.get("filename") or "").strip().lower(): a for a in (atts or []) if isinstance(a, dict)}
                        fetched = []
                        for fn in wanted:
                            it = by_name.get(fn.lower())
                            if not it:
                                continue
                            dl = str(it.get("download_url") or "").strip()
                            if not dl:
                                continue
                            data = await asyncio.to_thread(conf_client.download_attachment, dl)
                            if data:
                                fetched.append({"image_bytes": data, "hint": page_title})
                        if fetched:
                            caps = await describe_images_batch(fetched, concurrency=2)
                            cap_lines = [c.strip() for c in caps if str(c or "").strip()]
                            if cap_lines:
                                clean = (clean + "\n\n## Images\n" + "\n".join([f"- {c}" for c in cap_lines])).strip()
                except Exception:
                    pass

            # Stable Confluence URL by pageId (avoid title-based webui links).
            base = (settings.CONFLUENCE_URL or "").rstrip("/")
            web_ui = (page.get("_links") or {}).get("webui", "") if isinstance(page, dict) else ""
            wiki_prefix = "/wiki" if isinstance(web_ui, str) and web_ui.startswith("/spaces/") and not base.endswith("/wiki") else ""
            stable_url = f"{base}{wiki_prefix}/pages/viewpage.action?pageId={page_id}" if base else ""

            tasks = await extract_tasks_from_content(
                content=clean,
                source_type="confluence",
                client=http_client,
                source_ref=page_id,
            )

            for task in tasks:
                suggested_assignee = task.suggested_assignee
                if not suggested_assignee:
                    suggested_assignee = await repo.suggest_assignee_from_history(labels=task.labels or [])

                issue_type = _suggest_issue_type_from_labels(task.labels)
                epic_key = _detect_epic_key(f"{task.title}\n{task.description}\n{page_title}")
                draft_id = await repo.create_draft(
                    title=task.title,
                    description=task.description,
                    source_type="confluence",
                    source_ref=page_id,
                    source_summary=f"[{page_title}] {clean[:300]}",
                    source_url=stable_url or None,
                    scope_group_id=f"group_confluence_space_{str(space_key or '').strip().lower()}",
                    source_meta={
                        "space_key": space_key,
                        "page_id": page_id,
                        "title": page_title,
                        "stable_url": stable_url,
                        "evidence": (task.evidence or "").strip() or clean[:260],
                    },
                    evidence=[
                        {
                            "source": "confluence",
                            "url": stable_url,
                            "quote": (task.evidence or "").strip() or clean[:360],
                            "ref": {"space_key": space_key, "page_id": page_id},
                        }
                    ],
                    issue_type=issue_type,
                    epic_key=epic_key,
                    suggested_assignee=suggested_assignee,
                    priority=task.priority,
                    labels=task.labels,
                    triggered_by=triggered_by,
                    created_by=created_by,
                )
                if draft_id:
                    total += 1

    return total
