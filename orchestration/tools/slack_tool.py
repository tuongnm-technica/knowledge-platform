"""
orchestration/tools/slack_tool.py
Tool: get_slack_messages — lấy tin nhắn từ Slack channel theo ngày.
"""
from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from config.settings import settings
from datetime import datetime, timedelta, timezone
import httpx
import structlog

log = structlog.get_logger()


class GetSlackMessagesTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_slack_messages",
            description=(
                "Lấy tin nhắn Slack từ một channel trong khoảng thời gian nhất định. "
                "Dùng khi user hỏi về nội dung thảo luận, meeting notes, quyết định trong Slack."
            ),
            parameters={
                "channel_name": "Tên channel (ví dụ: general, engineering, hr-internal)",
                "days_back":    "Lấy bao nhiêu ngày trước (mặc định: 1, tối đa: 7)",
                "limit":        "Số tin nhắn tối đa (mặc định: 30)",
            },
        )

    async def run(self, channel_name: str, days_back: int = 1,
                  limit: int = 30, **_) -> ToolResult:
        headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # 1. Tìm channel ID
                channel_id = await self._find_channel(client, headers, channel_name)
                if not channel_id:
                    return ToolResult(success=False, data=[], summary="",
                                      error=f"Không tìm thấy channel: {channel_name}")

                # 2. Lấy messages
                oldest = (datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp()
                resp   = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={
                        "channel":  channel_id,
                        "oldest":   str(oldest),
                        "limit":    min(limit, 100),
                        "inclusive": True,
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    return ToolResult(success=False, data=[], summary="",
                                      error=data.get("error", "Slack API error"))

                # 3. Lấy user names
                messages = data.get("messages", [])
                user_map = await self._get_user_names(client, headers,
                           {m.get("user", "") for m in messages if m.get("user")})

                # 4. Format
                formatted = []
                for m in reversed(messages):  # chronological order
                    if m.get("type") != "message" or m.get("subtype"):
                        continue
                    ts   = datetime.fromtimestamp(float(m.get("ts", 0)), tz=timezone.utc)
                    name = user_map.get(m.get("user", ""), "Unknown")
                    text = m.get("text", "").strip()
                    if text:
                        formatted.append({
                            "time":    ts.strftime("%H:%M"),
                            "user":    name,
                            "text":    text[:300],
                        })

                if not formatted:
                    return ToolResult(success=True, data=[],
                                      summary=f"Không có tin nhắn nào trong #{channel_name} {days_back} ngày qua")

                lines = [f"#{channel_name} — {days_back} ngày qua ({len(formatted)} tin nhắn):"]
                for m in formatted[-20:]:  # last 20
                    lines.append(f"  [{m['time']}] {m['user']}: {m['text']}")

                log.info("tool.get_slack_messages", channel=channel_name, count=len(formatted))
                return ToolResult(success=True, data=formatted, summary="\n".join(lines))

        except Exception as e:
            log.error("tool.get_slack_messages.error", error=str(e))
            return ToolResult(success=False, data=[], summary="", error=str(e))

    async def _find_channel(self, client, headers, name: str) -> str | None:
        cursor = None
        name_lower = name.lower().lstrip("#")
        for _ in range(5):
            params = {"types": "public_channel,private_channel", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get("https://slack.com/api/conversations.list",
                                    headers=headers, params=params)
            data = resp.json()
            for ch in data.get("channels", []):
                if ch.get("name", "").lower() == name_lower:
                    return ch["id"]
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
        return None

    async def _get_user_names(self, client, headers, user_ids: set) -> dict:
        result = {}
        for uid in user_ids:
            if not uid:
                continue
            try:
                r = await client.get("https://slack.com/api/users.info",
                                     headers=headers, params={"user": uid})
                d = r.json()
                if d.get("ok"):
                    result[uid] = d["user"].get("real_name") or d["user"].get("name", uid)
            except Exception:
                result[uid] = uid
        return result