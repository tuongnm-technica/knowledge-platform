import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from connectors.slack.slack_permissions import SlackPermissions
from config.settings import settings
import structlog

log = structlog.get_logger()

# ─── Whitelist channels muốn sync ─────────────────────────────────────────────
# Để trống [] = sync tất cả channels bot có quyền
ALLOWED_CHANNEL_NAMES = [
    # "general",
    # "engineering",
    # "product",
]


class SlackConnector(BaseConnector):

    def __init__(self):
        self.validate_config()
        self._client = SlackClient()
        self._parser = SlackParser()
        self._permissions = SlackPermissions(self._client)

    def validate_config(self) -> bool:
        if not settings.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        all_channels = await self._client.get_channels()

        # Lọc theo whitelist nếu có
        if ALLOWED_CHANNEL_NAMES:
            channels = [c for c in all_channels if c.get("name") in ALLOWED_CHANNEL_NAMES]
        else:
            channels = all_channels

        log.info("slack.fetch.start", total=len(all_channels), syncing=len(channels))

        for channel in channels:
            channel_id   = channel["id"]
            channel_name = channel.get("name", channel_id)
            is_private   = channel.get("is_private", False)
            is_im        = channel.get("is_im", False)

            log.info("slack.fetch.channel", name=channel_name, private=is_private)

            messages = await self._client.get_messages(channel_id, limit=200)
            permissions = await self.get_permissions(channel_id)

            # Group messages thành document theo ngày
            grouped = self._group_by_day(messages)

            for date_str, day_messages in grouped.items():
                content = self._parser.extract_thread_content(day_messages)
                if not content or len(content) < 20:
                    continue

                display_name = f"DM" if is_im else f"#{channel_name}"
                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.SLACK,
                    source_id=f"{channel_id}_{date_str}",
                    title=f"[Slack] {display_name} — {date_str}",
                    content=content,
                    url=f"https://app.slack.com/client/{channel_id}",
                    author="slack",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    metadata={
                        "channel_id":   channel_id,
                        "channel_name": channel_name,
                        "date":         date_str,
                        "is_private":   is_private,
                        "message_count": len(day_messages),
                    },
                    permissions=permissions,
                )
                documents.append(doc)

            log.info("slack.channel.done", channel=channel_name, messages=len(messages))

        log.info("slack.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        return await self._permissions.get_permitted_groups(source_id)

    def _group_by_day(self, messages: list[dict]) -> dict[str, list[dict]]:
        """Group messages theo ngày để tạo document hợp lý."""
        grouped: dict[str, list[dict]] = {}
        for msg in messages:
            ts = msg.get("ts", "0")
            try:
                dt = datetime.fromtimestamp(float(ts))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = "unknown"
            grouped.setdefault(date_str, []).append(msg)
        return grouped