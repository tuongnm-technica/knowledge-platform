import re


class TextCleaner:
    def clean(self, text: str) -> str:
        text = self._remove_scripts(text)
        text = self._remove_html(text)
        text = self._normalize_whitespace(text)
        return text.strip()

    def _remove_scripts(self, text: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def _remove_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text)

    def _normalize_whitespace(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text