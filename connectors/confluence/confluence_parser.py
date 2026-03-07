import re


class ConfluenceParser:

    def parse(self, html_body: str) -> str:
        text = self._strip_macros(html_body)
        text = self._strip_tags(text)
        text = self._clean_whitespace(text)
        return text

    def _strip_macros(self, text: str) -> str:
        return re.sub(r"<ac:[^>]+>.*?</ac:[^>]+>", "", text, flags=re.DOTALL)

    def _strip_tags(self, text: str) -> str:
        text = re.sub(r"<(p|br|li|tr|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
        return re.sub(r"<[^>]+>", "", text)

    def _clean_whitespace(self, text: str) -> str:
        lines = [ln.strip() for ln in text.splitlines()]
        return "\n".join(ln for ln in lines if ln)