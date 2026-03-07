import re


class SlackParser:

    def parse_message(self, message: dict) -> str:
        text = message.get("text", "")
        text = self._remove_mentions(text)
        text = self._remove_special_chars(text)
        return text.strip()

    def _remove_mentions(self, text: str) -> str:
        return re.sub(r"<@[A-Z0-9]+>", "@user", text)

    def _remove_special_chars(self, text: str) -> str:
        text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
        text = re.sub(r"<http[^|>]+\|([^>]+)>", r"\1", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        return text

    def extract_thread_content(self, messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            text = self.parse_message(msg)
            if text:
                user = msg.get("user", "unknown")
                parts.append(f"[{user}]: {text}")
        return "\n".join(parts)