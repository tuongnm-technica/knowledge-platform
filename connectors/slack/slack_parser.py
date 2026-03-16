import re
from datetime import datetime


class SlackParser:

    def extract_thread_content(
        self,
        messages: list[dict],
        user_cache: dict,
        channel_name: str,
        date_str: str = "",
    ) -> str:
        """
        Chuyển list messages thành text có cấu trúc cho RAG.
        Format: [HH:MM] Tên (username): nội dung
        """
        parts = []

        # Header
        if date_str:
            parts.append(f"=== #{channel_name} | {date_str} ===\n")

        for msg in messages:
            # Bỏ qua bot message, join/leave events
            if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave",
                                       "channel_archive", "channel_unarchive"):
                continue

            text = self._clean_text(msg.get("text", ""))
            if not text:
                continue

            sender    = self._get_sender(msg, user_cache)
            timestamp = self._format_time(msg.get("ts"))
            ts_raw = str(msg.get("ts") or "").strip()

            # Include ts so we can build stable Slack deep links (p+timestamp) per chunk.
            # Format: [09:30|1710561234.567890] Tu Nguyen (tuongnm): nội dung
            line = f"[{timestamp}|{ts_raw}] {sender}: {text}" if ts_raw else f"[{timestamp}] {sender}: {text}"
            parts.append(line)

            # Attachments / file shares
            for attachment in msg.get("attachments", []):
                att_text = attachment.get("text") or attachment.get("fallback") or ""
                if att_text:
                    parts.append(f"  → {att_text.strip()}")

        return "\n".join(parts)

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        # Chuyển mention <@U123> thành @username nếu có thể
        text = re.sub(r"<@([A-Z0-9]+)>", r"@\1", text)

        # Giữ lại URL dạng readable: <https://example.com|tên> → tên (https://example.com)
        text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)

        # URL không có label
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)

        # Bỏ channel mention <#C123|channel-name> → #channel-name
        text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)

        # Bỏ emoji code nhưng giữ text emoji
        text = re.sub(r":([a-z0-9_\-+]+):", "", text)

        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _get_sender(self, msg: dict, user_cache: dict) -> str:
        uid  = msg.get("user") or msg.get("bot_id")
        if not uid:
            return "unknown"

        info        = user_cache.get(uid, {})
        display     = info.get("display_name", "").strip()
        real_name   = info.get("real_name", "").strip()
        username    = info.get("name", "").strip()

        name = display or real_name or username or uid

        # Format: Tên (username) nếu có cả 2
        if (display or real_name) and username and username != (display or real_name):
            return f"{name} ({username})"
        return name

    def _format_time(self, ts: str) -> str:
        try:
            dt = datetime.fromtimestamp(float(ts))
            return dt.strftime("%H:%M")
        except Exception:
            return "--:--"
