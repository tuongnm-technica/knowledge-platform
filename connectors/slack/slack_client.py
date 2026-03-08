from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from config.settings import settings
import structlog

log = structlog.get_logger()


class SlackClient:
    def __init__(self):
        if not settings.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        self._client = AsyncWebClient(token=settings.SLACK_BOT_TOKEN)

    async def get_channels(self) -> list[dict]:
        """Lấy tất cả public + private channels bot có quyền truy cập."""
        channels = []
        cursor = None
        try:
            while True:
                kwargs = dict(
                    types="public_channel,private_channel,mpim,im",
                    limit=200,
                    exclude_archived=True,
                )
                if cursor:
                    kwargs["cursor"] = cursor

                result = await self._client.conversations_list(**kwargs)
                channels.extend(result["channels"])

                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except SlackApiError as e:
            log.error("slack.get_channels.failed", error=str(e))
        return channels

    async def get_messages(self, channel_id: str, limit: int = 200) -> list[dict]:
        """Lấy messages kèm thread replies."""
        messages = []
        try:
            result = await self._client.conversations_history(
                channel=channel_id,
                limit=limit,
            )
            raw_messages = result.get("messages", [])

            for msg in raw_messages:
                messages.append(msg)
                # Lấy thread replies nếu có
                if msg.get("reply_count", 0) > 0:
                    replies = await self.get_thread_replies(channel_id, msg["ts"])
                    messages.extend(replies[1:])  # bỏ message gốc (đã có rồi)

        except SlackApiError as e:
            log.error("slack.get_messages.failed", channel=channel_id, error=str(e))
        return messages

    async def get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        """Lấy toàn bộ replies trong một thread."""
        try:
            result = await self._client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
            )
            return result.get("messages", [])
        except SlackApiError as e:
            log.error("slack.get_replies.failed", channel=channel_id, error=str(e))
            return []

    async def get_channel_members(self, channel_id: str) -> list[str]:
        try:
            result = await self._client.conversations_members(channel=channel_id)
            return result.get("members", [])
        except SlackApiError as e:
            log.error("slack.get_members.failed", channel=channel_id, error=str(e))
            return []

    async def get_user_info(self, user_id: str) -> dict:
        try:
            result = await self._client.users_info(user=user_id)
            return result.get("user", {})
        except SlackApiError as e:
            log.error("slack.get_user.failed", user=user_id, error=str(e))
            return {}

    def test_connection_sync(self) -> bool:
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._client.auth_test())
            return result["ok"]
        except Exception as e:
            log.error("slack.test_connection.failed", error=str(e))
            return False