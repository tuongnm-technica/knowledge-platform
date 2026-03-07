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
        try:
            result = await self._client.conversations_list(
                types="public_channel,private_channel"
            )
            return result["channels"]
        except SlackApiError as e:
            log.error("slack.get_channels.failed", error=str(e))
            return []

    async def get_messages(self, channel_id: str, limit: int = 200) -> list[dict]:
        try:
            result = await self._client.conversations_history(
                channel=channel_id, limit=limit
            )
            return result["messages"]
        except SlackApiError as e:
            log.error("slack.get_messages.failed", channel=channel_id, error=str(e))
            return []

    async def get_channel_members(self, channel_id: str) -> list[str]:
        try:
            result = await self._client.conversations_members(channel=channel_id)
            return result["members"]
        except SlackApiError as e:
            log.error("slack.get_members.failed", channel=channel_id, error=str(e))
            return []