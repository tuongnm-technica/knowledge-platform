import uuid
from collections import defaultdict
from datetime import datetime

import structlog

from config.settings import settings
from connectors.base.base_connector import BaseConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from models.document import Document, SourceType
from permissions.workspace_config import get_slack_workspace


log = structlog.get_logger()


class SlackConnector(BaseConnector):
    def __init__(self, *, channel_ids: set[str] | None = None, bot_token: str | None = None):
        self._client = SlackClient(bot_token=bot_token)
        self._parser = SlackParser()
        self._channel_ids = {cid.strip() for cid in (channel_ids or set()) if cid and str(cid).strip()}

    def validate_config(self) -> bool:
        # SlackClient constructor already validates presence of token.
        return True

    async def get_permissions(self, source_id: str) -> list[str]:
        channel_id = source_id.split("_")[0] if "_" in source_id else source_id
        return [f"group_slack_channel_{str(channel_id or '').strip().lower()}"]

    async def fetch_documents(self) -> list[Document]:
        documents = []
        channels = await self._client.get_channels()
        if self._channel_ids:
            channels = [c for c in channels if c.get("id") in self._channel_ids]

        log.info("slack.fetch.start", total_channels=len(channels))

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)

            try:
                messages = await self._client.get_messages(channel_id, days=90)
                if not messages:
                    continue

                daily_messages: dict[str, list[dict]] = defaultdict(list)
                for msg in messages:
                    ts = float(msg.get("ts", 0))
                    date_key = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    daily_messages[date_key].append(msg)

                user_cache = self._client.get_user_cache()
                members = await self._client.get_channel_members(channel_id)

                for date_str, msgs in daily_messages.items():
                    msgs.reverse()
                    participants = self._extract_participants(msgs, user_cache)

                    first_ts = self._first_indexable_ts(msgs)
                    deep_link = self._slack_deep_link(channel_id, first_ts) if first_ts else f"https://slack.com/archives/{channel_id}"

                    # Collect image files referenced in the day's messages (screenshots, diagrams).
                    files_by_id: dict[str, dict] = {}
                    for msg in msgs:
                        for f in (msg.get("files") or []):
                            try:
                                mimetype = str(f.get("mimetype") or "").strip().lower()
                                if not mimetype.startswith("image/"):
                                    continue
                                fid = str(f.get("id") or "").strip()
                                if not fid:
                                    continue
                                files_by_id[fid] = {
                                    "id": fid,
                                    "name": str(f.get("name") or f.get("title") or "image").strip(),
                                    "mimetype": mimetype,
                                    "size": int(f.get("size") or 0) or None,
                                    "url_private": str(f.get("url_private") or "").strip(),
                                    "url_private_download": str(f.get("url_private_download") or "").strip(),
                                }
                            except Exception:
                                continue

                    content = self._parser.extract_thread_content(
                        msgs,
                        user_cache=user_cache,
                        channel_name=channel_name,
                        date_str=date_str,
                    )
                    if not content or len(content.strip()) < 10:
                        continue

                    documents.append(
                        Document(
                            id=str(uuid.uuid4()),
                            source=SourceType.SLACK,
                            source_id=f"{channel_id}_{date_str}",
                            title=f"[Slack] #{channel_name} | Ngay {date_str}",
                            content=content,
                            url=deep_link,
                            author="slack",
                            created_at=datetime.strptime(date_str, "%Y-%m-%d"),
                            updated_at=datetime.utcnow(),
                            metadata={
                                "channel_id": channel_id,
                                "channel_name": channel_name,
                                "date": date_str,
                                "message_count": len(msgs),
                                "first_ts": first_ts or "",
                                "deep_link": deep_link,
                                "members": members,
                                "participants": participants,
                                "slack_files": list(files_by_id.values()),
                            },
                            permissions=[f"group_slack_channel_{str(channel_id or '').strip().lower()}"],
                            workspace_id=get_slack_workspace(channel_name),
                        )
                    )

                log.info("slack.channel.done", channel=channel_name, total_days=len(daily_messages))

            except Exception as e:
                log.error("slack.channel.failed", channel=channel_name, error=str(e))
                continue

        log.info("slack.fetch.done", total_documents=len(documents))
        return documents

    @staticmethod
    def _first_indexable_ts(messages: list[dict]) -> str | None:
        for msg in messages:
            if msg.get("subtype") in (
                "bot_message",
                "channel_join",
                "channel_leave",
                "channel_archive",
                "channel_unarchive",
            ):
                continue
            ts = str(msg.get("ts") or "").strip()
            text = str(msg.get("text") or "").strip()
            attachments = msg.get("attachments") or []
            if ts and (text or attachments):
                return ts
        return None

    @staticmethod
    def _slack_deep_link(channel_id: str, ts: str) -> str:
        """
        Slack message deep link.
        Format: https://slack.com/archives/{channel}/p{tsDigits} where tsDigits = ts without dot.
        """
        ts = str(ts or "").strip()
        if not ts:
            return f"https://slack.com/archives/{channel_id}"
        if "." in ts:
            sec, frac = ts.split(".", 1)
            frac = (frac + "000000")[:6]  # Slack ts is seconds.microseconds
            ts_digits = f"{sec}{frac}"
        else:
            ts_digits = "".join([c for c in ts if c.isdigit()])
        return f"https://slack.com/archives/{channel_id}/p{ts_digits}"

    @staticmethod
    def _extract_participants(messages: list[dict], user_cache: dict[str, dict]) -> list[dict]:
        participants: list[dict] = []
        seen: set[str] = set()

        for msg in messages:
            user_id = msg.get("user")
            if not user_id or user_id in seen:
                continue

            seen.add(user_id)
            info = user_cache.get(user_id, {})
            participant = {
                "user_id": user_id,
                "display_name": info.get("display_name", ""),
                "real_name": info.get("real_name", ""),
                "name": info.get("name", ""),
                "email": info.get("email", ""),
            }
            if any(participant.values()):
                participants.append(participant)

        return participants
