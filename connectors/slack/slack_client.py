from datetime import datetime, timedelta
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from config.settings import settings
import structlog

log = structlog.get_logger()

# Lấy 3 tháng gần nhất
SYNC_DAYS = 90


class SlackClient:
    def __init__(self, *, bot_token: str | None = None):
        token = (bot_token or settings.SLACK_BOT_TOKEN or "").strip()
        if not token:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        self._client     = AsyncWebClient(token=token)
        self._user_cache: dict[str, dict] = {}

    async def get_channels(self) -> list[dict]:
        channels = []
        cursor   = None
        try:
            while True:
                kwargs = dict(types="public_channel,private_channel", limit=200, exclude_archived=True)
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

    async def test_connection(self) -> bool:
        try:
            await self._client.auth_test()
            return True
        except SlackApiError as e:
            log.error("slack.test_connection.failed", error=str(e))
            return False

    async def get_channel_members(self, channel_id: str) -> list[str]:
        try:
            result = await self._client.conversations_members(channel=channel_id)
            return result.get("members", [])
        except SlackApiError as e:
            log.error("slack.get_members.failed", channel=channel_id, error=str(e))
            return []

    async def get_messages(self, channel_id: str, days: int = SYNC_DAYS) -> list[dict]:
        """
        Lấy toàn bộ messages trong N ngày gần nhất, có phân trang.
        Default: 90 ngày (3 tháng)
        """
        messages = []
        oldest   = str((datetime.utcnow() - timedelta(days=days)).timestamp())
        cursor   = None

        try:
            while True:
                kwargs = dict(
                    channel = channel_id,
                    limit   = 200,       # max per page
                    oldest  = oldest,    # ← chỉ lấy từ mốc thời gian này
                )
                if cursor:
                    kwargs["cursor"] = cursor

                result       = await self._client.conversations_history(**kwargs)
                raw_messages = result.get("messages", [])

                # Cache user info
                user_ids = {m.get("user") for m in raw_messages if m.get("user")}
                await self._cache_users(user_ids)

                # Lấy thread replies cho mỗi message
                for msg in raw_messages:
                    messages.append(msg)
                    if msg.get("reply_count", 0) > 0:
                        replies = await self.get_thread_replies(channel_id, msg["ts"])
                        await self._cache_users({m.get("user") for m in replies if m.get("user")})
                        messages.extend(replies[1:])  # bỏ message đầu (trùng với parent)

                # Phân trang
                cursor = result.get("response_metadata", {}).get("next_cursor")
                has_more = result.get("has_more", False)

                log.info("slack.get_messages.page",
                         channel=channel_id,
                         fetched=len(raw_messages),
                         total_so_far=len(messages),
                         has_more=has_more)

                if not has_more or not cursor:
                    break

        except SlackApiError as e:
            log.error("slack.get_messages.failed", channel=channel_id, error=str(e))

        log.info("slack.get_messages.done", channel=channel_id, total=len(messages), days=days)
        return messages

    async def get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        try:
            result = await self._client.conversations_replies(channel=channel_id, ts=thread_ts)
            return result.get("messages", [])
        except SlackApiError as e:
            log.error("slack.get_replies.failed", error=str(e))
            return []

    async def _cache_users(self, user_ids: set[str]) -> None:
        for uid in user_ids:
            if uid and uid not in self._user_cache:
                try:
                    result  = await self._client.users_info(user=uid)
                    user = result.get("user", {})
                    profile = result.get("user", {}).get("profile", {})
                    self._user_cache[uid] = {
                        "user_id": uid,
                        "display_name": profile.get("display_name", ""),
                        "real_name":    profile.get("real_name", ""),
                        "name":         user.get("name", ""),
                        "email":        profile.get("email", ""),
                    }
                except Exception:
                    self._user_cache[uid] = {}

    def get_user_cache(self) -> dict[str, dict]:
        return self._user_cache
