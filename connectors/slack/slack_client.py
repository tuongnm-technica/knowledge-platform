from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from config.settings import settings
from datetime import datetime, timedelta
import structlog

log = structlog.get_logger()

# Để trống = sync TẤT CẢ channels bot được add vào
# Điền vào để chỉ sync những channels cụ thể
ALLOWED_CHANNEL_NAMES: list[str] = []

# Lần full sync đầu tiên: lấy 3 tháng gần nhất
FULL_SYNC_DAYS = 90


class SlackClient:
    def __init__(self):
        if not settings.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        self._client = AsyncWebClient(token=settings.SLACK_BOT_TOKEN)

    async def get_channels(self) -> list[dict]:
        """Lấy public + private channels bot được add vào."""
        channels = []
        cursor   = None
        try:
            while True:
                kwargs = dict(
                    types="public_channel,private_channel",
                    limit=200,
                    exclude_archived=True,
                )
                if cursor:
                    kwargs["cursor"] = cursor

                result  = await self._client.conversations_list(**kwargs)
                all_ch  = result["channels"]

                # Lọc whitelist nếu có cấu hình
                if ALLOWED_CHANNEL_NAMES:
                    all_ch = [c for c in all_ch if c.get("name") in ALLOWED_CHANNEL_NAMES]

                channels.extend(all_ch)
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except SlackApiError as e:
            log.error("slack.get_channels.failed", error=str(e))
        return channels

    async def get_messages(
        self,
        channel_id: str,
        last_sync: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Lấy messages:
        - last_sync=None → 3 tháng gần nhất (FULL_SYNC_DAYS=90)
        - last_sync=<dt> → chỉ lấy messages SAU last_sync (incremental)
        """
        messages = []

        if last_sync:
            oldest_ts = str(last_sync.timestamp())
            log.info("slack.messages.incremental", channel=channel_id,
                     since=last_sync.isoformat())
        else:
            since_dt  = datetime.utcnow() - timedelta(days=FULL_SYNC_DAYS)
            oldest_ts = str(since_dt.timestamp())
            log.info("slack.messages.full_sync", channel=channel_id,
                     since=since_dt.strftime("%Y-%m-%d"), days=FULL_SYNC_DAYS)

        try:
            cursor = None
            while True:
                kwargs = dict(
                    channel=channel_id,
                    limit=200,           # Slack max 200/request
                    oldest=oldest_ts,
                )
                if cursor:
                    kwargs["cursor"] = cursor

                result = await self._client.conversations_history(**kwargs)
                batch  = result.get("messages", [])

                # Lấy thread replies nếu có
                for msg in batch:
                    if msg.get("reply_count", 0) > 0:
                        replies = await self._get_thread_replies(channel_id, msg["ts"])
                        messages.extend(replies[1:])  # bỏ message gốc (đã có trong batch)

                messages.extend(batch)

                has_more = result.get("has_more", False)
                cursor   = result.get("response_metadata", {}).get("next_cursor")
                if not has_more or not cursor or len(messages) >= limit:
                    break

        except SlackApiError as e:
            log.error("slack.get_messages.failed", channel=channel_id, error=str(e))

        log.info("slack.messages.fetched", channel=channel_id, count=len(messages))
        return messages

    async def _get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        try:
            result = await self._client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )
            return result.get("messages", [])
        except SlackApiError:
            return []

    async def get_channel_members(self, channel_id: str) -> list[str]:
        try:
            result = await self._client.conversations_members(channel=channel_id)
            return result.get("members", [])
        except SlackApiError:
            return []