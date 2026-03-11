import re
from datetime import datetime


class SlackParser:

    def extract_thread_content(
        self,
        messages: list[dict],
        user_cache: dict,
        channel_name: str,
    ) -> str:

        parts = []

        for msg in messages:

            if msg.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                continue

            text = self._clean_text(msg.get("text", ""))
            if not text:
                continue

            sender = self._get_sender(msg, user_cache)
            time = self._format_time(msg.get("ts"))

            parts.append(
                f"""
channel: {channel_name}
sender: {sender}
time: {time}

{text}
"""
            )

        return "\n".join(parts)

    def _clean_text(self, text):

        text = re.sub(r"<@[^>]+>", "", text)
        text = re.sub(r"<https?://[^>]+>", "", text)
        text = re.sub(r":[a-z_]+:", "", text)

        return text.strip()

    def _get_sender(self, msg, user_cache):

        uid = msg.get("user")

        if not uid:
            return "unknown"

        info = user_cache.get(uid, {})

        display = info.get("display_name") or info.get("real_name")
        username = info.get("name")

        if display and username:
            return f"{display} ({username})"

        return display or username or uid

    def _format_time(self, ts):

        try:
            dt = datetime.fromtimestamp(float(ts))
            return dt.strftime("%H:%M")
        except:
            return ""