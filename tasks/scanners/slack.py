from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
import httpx
import structlog

from config.settings import settings
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from tasks.extractor import extract_tasks_from_content, detect_action_signal
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
                # Layer 2: Context Builder - Group by thread_ts to create meaningful Context Blocks
                blocks = defaultdict(list)
                for msg in msgs:
                    thread_ts = str(msg.get("thread_ts") or msg.get("ts") or "").strip()
                    if thread_ts:
                        blocks[thread_ts].append(msg)

                for thread_ts, block_msgs in blocks.items():
                    block_msgs.sort(key=lambda m: float(m.get("ts", 0) or 0))
                    content = parser.extract_thread_content(block_msgs, user_cache=user_cache, channel_name=channel_name, date_str=date_key)
                    
                    if not content or len(content.strip()) < 50:
                        continue

                    # Anti-spam guard: skip thread nếu đã được xử lý trong 7 ngày.
                    # Dùng thread_ts làm key để nhất quán với scan_thread().
                    source_ref_key = f"#{channel_name} thread:{thread_ts}"
                    already_processed = await self.repo.has_recent_tasks(source_ref_key, minutes=10080)  # 7 days
                    if already_processed:
                        log.info("scanner.slack.scan.skipped_already_processed", channel=channel_name, thread_ts=thread_ts)
                        continue

                    # Layer 3: Signal Detection
                    has_action = await detect_action_signal(content, self.llm_client)
                    if not has_action:
                        log.debug("scanner.slack.signal_drop", channel=channel_name, thread_ts=thread_ts)
                        continue

                    first_ts = next((str(m.get("ts") or "").strip() for m in block_msgs if m.get("subtype") not in ("bot_message", "channel_join", "channel_leave", "channel_archive", "channel_unarchive") and (str(m.get("text") or "").strip() or m.get("attachments"))), None)
                    base_url = self._slack_deep_link(channel_id, first_ts) if first_ts else self._slack_deep_link(channel_id, "")

                    # Layer 4: Task Extraction - dùng source_ref_key nhất quán với has_recent_tasks
                    tasks = await extract_tasks_from_content(content=content, source_type="slack", llm_client=self.llm_client, source_ref=source_ref_key)

                    async def _save_task(t, parent_id=None) -> list[str]:
                        suggested_assignee = await self._resolve_slack_users(t.suggested_assignee, headers) if t.suggested_assignee else await self.repo.suggest_assignee_from_history(labels=t.labels or [])
                        evidence_ts = (t.evidence_ts or "").strip()
                        source_url = self._slack_deep_link(channel_id, evidence_ts) if evidence_ts else base_url

                        quote = (t.evidence or "").strip()
                        if not quote and evidence_ts and content:
                            needle = f"|{evidence_ts}]"
                            quote = next((line.strip() for line in content.splitlines() if needle in line), "")

                        draft_id = await self.repo.create_draft(
                            title=t.title,
                            description=t.description,
                            source_type="slack",
                            source_ref=source_ref_key,  # dùng source_ref_key nhất quán để dedup
                            source_summary=content[:300],
                            source_url=source_url,
                            scope_group_id=f"group_slack_channel_{str(channel_id or '').strip().lower()}",
                            parent_draft_id=parent_id,
                            source_meta={
                                "channel_id": channel_id,
                                "channel_name": channel_name,
                                "date": date_key,
                                "evidence_ts": evidence_ts,
                                "evidence": quote,
                                "thread_ts": thread_ts,
                            },
                            evidence=[{
                                "source": "slack",
                                "url": source_url,
                                "quote": quote or content[:300],
                                "ref": {"channel_id": channel_id, "ts": evidence_ts, "thread_ts": thread_ts},
                            }],
                            issue_type=self._suggest_issue_type_from_labels(t.labels),
                            epic_key=self._detect_epic_key(f"{t.title}\n{t.description}"),
                            suggested_assignee=suggested_assignee,
                            priority=t.priority,
                            labels=t.labels,
                            triggered_by=triggered_by,
                            created_by=created_by,
                        )
                        saved_ids = []
                        if draft_id:
                            saved_ids.append(draft_id)
                            for st in (t.subtasks or []):
                                st_ids = await _save_task(st, draft_id)
                                saved_ids.extend(st_ids)
                        return saved_ids

                    saved_task_titles = []
                    for task in tasks:
                        # Harden: lọc nếu độ tin cậy thấp hoặc mô tả quá ngắn (tránh junk/social chat)
                        if task.confidence < 0.7 or len(task.description or "") < 40:
                            log.debug("scanner.slack.scan.filtered_junk", title=task.title, confidence=task.confidence, desc_len=len(task.description or ""))
                            continue

                        t_ids = await _save_task(task)
                        if t_ids:
                            total += len(t_ids)
                            saved_task_titles.append(task.title)

                    # Chỉ reply nếu thực sự tạo được draft mới (không reply nếu bị dedup bởi create_draft)
                    if saved_task_titles and thread_ts:
                        titles_str = "\n".join(f"• *{tt}*" for tt in saved_task_titles)
                        msg = f"🤖 *[Knowledge Platform]*\nTớ đã quét luồng thảo luận này và bóc tách thành các Draft Task:\n{titles_str}\n\n👉 Mọi người vào hệ thống duyệt để tớ đồng bộ sang Jira nhé!"
                        await client.reply_to_thread(channel_id, thread_ts, msg)
                        
        return total

    async def scan_thread(self, channel_id: str, thread_ts: str, triggered_by: str = "slack_event", created_by: str | None = None) -> int:
        """Thực thi quét chủ động cho 1 thread Slack cụ thể do Event API kích hoạt."""
        if not settings.SLACK_BOT_TOKEN:
            log.warning("scanner.slack.no_token")
            return 0
            
        client = SlackClient()
        parser = SlackParser()
        user_cache = client.get_user_cache()

        msgs = await client.get_thread_replies(channel_id, thread_ts)
        if not msgs:
            return 0
            
        channel_name = channel_id
        try:
            chan_info = await client._client.conversations_info(channel=channel_id)
            if chan_info.get("ok"):
                channel_name = chan_info.get("channel", {}).get("name", channel_id)
        except Exception:
            pass

        date_key = datetime.now().strftime("%Y-%m-%d")
        content = parser.extract_thread_content(msgs, user_cache=user_cache, channel_name=channel_name, date_str=date_key)
        
        if not content or len(content.strip()) < 50:
            return 0
            
        # Anti-spam guard: skip if we already created tasks for this exact thread in the last 7 days.
        # This works even if the task was rejected/dismissed (soft-delete).
        source_ref_key = f"#{channel_name} thread:{thread_ts}"
        already_processed = await self.repo.has_recent_tasks(source_ref_key, minutes=10080)
        if already_processed:
            log.info("scanner.slack.scan_thread.skipped_already_processed", channel=channel_name, thread_ts=thread_ts)
            return 0

        has_action = await detect_action_signal(content, self.llm_client)
        if not has_action:
            log.debug("scanner.slack.scan_thread.no_action", channel=channel_name, thread_ts=thread_ts)
            return 0
            
        base_url = self._slack_deep_link(channel_id, thread_ts)
        # Layer 4: Task Extraction - dùng source_ref_key nhất quán (#channel thread:ts)
        tasks = await extract_tasks_from_content(content=content, source_type="slack", llm_client=self.llm_client, source_ref=source_ref_key)
        
        headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
        
        async def _save_task(t, parent_id=None) -> list[str]:
            suggested_assignee = await self._resolve_slack_users(t.suggested_assignee, headers) if t.suggested_assignee else await self.repo.suggest_assignee_from_history(labels=t.labels or [])
            evidence_ts = (t.evidence_ts or "").strip()
            source_url = self._slack_deep_link(channel_id, evidence_ts) if evidence_ts else base_url

            quote = (t.evidence or "").strip()
            if not quote and evidence_ts and content:
                needle = f"|{evidence_ts}]"
                quote = next((line.strip() for line in content.splitlines() if needle in line), "")

            draft_id = await self.repo.create_draft(
                title=t.title,
                description=t.description,
                source_type="slack",
                source_ref=source_ref_key,  # Dùng biến đã định nghĩa ở trên để nhất quán
                source_summary=content[:300],
                source_url=source_url,
                scope_group_id=f"group_slack_channel_{str(channel_id or '').strip().lower()}",
                parent_draft_id=parent_id,
                source_meta={
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "date": date_key,
                    "evidence_ts": evidence_ts,
                    "evidence": quote,
                    "thread_ts": thread_ts,
                },
                evidence=[{
                    "source": "slack",
                    "url": source_url,
                    "quote": quote or content[:300],
                    "ref": {"channel_id": channel_id, "ts": evidence_ts, "thread_ts": thread_ts},
                }],
                issue_type=self._suggest_issue_type_from_labels(t.labels),
                epic_key=self._detect_epic_key(f"{t.title}\n{t.description}"),
                suggested_assignee=suggested_assignee,
                priority=t.priority,
                labels=t.labels,
                triggered_by=triggered_by,
                created_by=created_by,
            )
            saved_ids = []
            if draft_id:
                saved_ids.append(draft_id)
                for st in (t.subtasks or []):
                    st_ids = await _save_task(st, draft_id)
                    saved_ids.extend(st_ids)
            return saved_ids

        saved_task_titles = []
        total = 0
        for task in tasks:
            # Harden: lọc nếu độ tin cậy thấp hoặc mô tả quá ngắn (webhook auto-trigger)
            if task.confidence < 0.7 or len(task.description or "") < 40:
                log.debug("scanner.slack.scan_thread.filtered_junk", title=task.title, confidence=task.confidence, desc_len=len(task.description or ""))
                continue

            t_ids = await _save_task(task)
            if t_ids:
                total += len(t_ids)
                saved_task_titles.append(task.title)

        if saved_task_titles and thread_ts:
            titles_str = "\n".join(f"• *{tt}*" for tt in saved_task_titles)
            msg = f"🤖 *[Knowledge Platform]*\nTớ vừa bóc tách nhanh Thread này theo yêu cầu (Webhook) và tạo các Draft Task:\n{titles_str}\n\n👉 Mọi người vào hệ thống duyệt để tớ đồng bộ sang Jira nhé!"
            await client.reply_to_thread(channel_id, thread_ts, msg)
            
        return total