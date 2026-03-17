from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
import httpx
import structlog

from config.settings import settings
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from tasks.extractor import extract_tasks_from_content
from .base import BaseScanner

log = structlog.get_logger()
_user_cache: dict[str, str] = {}


class SlackScanner(BaseScanner):
    
    def _slack_deep_link(self, channel_id: str, ts: str) -> str:
        ts = str(ts or "").strip()
        if not ts:
            return f"https://slack.com/archives/{channel_id}"
        if "." in ts:
            sec, frac = ts.split(".", 1)
            ts_digits = f"{sec}{(frac + '000000')[:6]}"
        else:
            ts_digits = "".join([c for c in ts if c.isdigit()])
        return f"https://slack.com/archives/{channel_id}/p{ts_digits}"

    async def _resolve_slack_users(self, text: str, headers: dict) -> str:
        user_ids = re.findall(r"@(U[A-Z0-9]+)", text)
        if not user_ids:
            return text

        async with httpx.AsyncClient(timeout=10) as client:
            for user_id in set(user_ids):
                if user_id in _user_cache:
                    continue
                try:
                    response = await client.get("https://slack.com/api/users.info", headers=headers, params={"user": user_id})
                    payload = response.json()
                    _user_cache[user_id] = payload["user"].get("real_name") or payload["user"].get("name", user_id) if payload.get("ok") else user_id
                except Exception:
                    _user_cache[user_id] = user_id

        result = text
        for user_id, name in _user_cache.items():
            result = result.replace(f"@{user_id}", f"@{name}")
        return result

    async def scan(self, days_back: int, triggered_by: str, created_by: str | None) -> int:
        if not settings.SLACK_BOT_TOKEN:
            log.warning("scanner.slack.no_token")
            return 0

        selection = await self._load_connector_selection("slack")
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

            by_date: dict[str, list[dict]] = defaultdict(list)
            for msg in messages:
                try: ts = float(msg.get("ts", 0))
                except Exception: ts = 0.0
                if ts: by_date[datetime.fromtimestamp(ts).strftime("%Y-%m-%d")].append(msg)

            for date_key, msgs in sorted(by_date.items(), key=lambda x: x[0], reverse=True):
                msgs.sort(key=lambda m: float(m.get("ts", 0) or 0))
                content = parser.extract_thread_content(msgs, user_cache=user_cache, channel_name=channel_name, date_str=date_key)
                
                if not content or len(content.strip()) < 50:
                    continue

                first_ts = next((str(m.get("ts") or "").strip() for m in msgs if m.get("subtype") not in ("bot_message", "channel_join", "channel_leave", "channel_archive", "channel_unarchive") and (str(m.get("text") or "").strip() or m.get("attachments"))), None)
                base_url = self._slack_deep_link(channel_id, first_ts) if first_ts else self._slack_deep_link(channel_id, "")

                tasks = await extract_tasks_from_content(content=content, source_type="slack", llm_client=self.llm_client, source_ref=f"#{channel_name} | {date_key}")

                for task in tasks:
                    suggested_assignee = await self._resolve_slack_users(task.suggested_assignee, headers) if task.suggested_assignee else await self.repo.suggest_assignee_from_history(labels=task.labels or [])
                    evidence_ts = (task.evidence_ts or "").strip()
                    source_url = self._slack_deep_link(channel_id, evidence_ts) if evidence_ts else base_url

                    quote = (task.evidence or "").strip()
                    if not quote and evidence_ts and content:
                        needle = f"|{evidence_ts}]"
                        quote = next((line.strip() for line in content.splitlines() if needle in line), "")

                    draft_id = await self.repo.create_draft(
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
                        evidence=[{
                            "source": "slack",
                            "url": source_url,
                            "quote": quote or content[:300],
                            "ref": {"channel_id": channel_id, "ts": evidence_ts},
                        }],
                        issue_type=self._suggest_issue_type_from_labels(task.labels),
                        epic_key=self._detect_epic_key(f"{task.title}\n{task.description}"),
                        suggested_assignee=suggested_assignee,
                        priority=task.priority,
                        labels=task.labels,
                        triggered_by=triggered_by,
                        created_by=created_by,
                    )
                    if draft_id: total += 1
        return total