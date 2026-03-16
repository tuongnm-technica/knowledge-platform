from bs4 import BeautifulSoup
import structlog

log = structlog.get_logger()


class ConfluenceParser:

    def parse(self, html_body: str) -> str:
        """Parse HTML thành plain text — dùng cho content chính."""
        if not html_body:
            return ""
        soup = BeautifulSoup(html_body, "html.parser")
        # Keep output stable and readable for indexing (headings + paragraphs).
        sections = self.parse_sections(html_body)
        if not sections:
            return self._extract_structured(soup)

        blocks = []
        for section in sections:
            title = (section.get("title") or "").strip()
            content = (section.get("content") or "").strip()
            if not content:
                continue
            if title:
                blocks.append(title)
            blocks.append(content)
        return "\n\n".join(blocks).strip()

    def parse_sections(self, html_body: str) -> list[dict]:
        """
        Parse HTML thành list sections theo cấu trúc heading.
        Mỗi section = {"title": ..., "content": ...}
        Dùng cho semantic chunking.
        """
        if not html_body:
            return []

        soup = BeautifulSoup(html_body, "html.parser")
        sections: list[dict] = []
        current_content: list[str] = []

        # Track heading hierarchy: H1 > H2 > H3 > H4
        heading_stack: dict[int, str] = {}
        current_title = ""

        def _heading_path() -> str:
            parts = [heading_stack.get(level, "") for level in (1, 2, 3, 4)]
            parts = [p for p in parts if p]
            return " > ".join(parts).strip()

        def _flush():
            nonlocal current_content, current_title
            joined = "\n".join([c for c in current_content if c]).strip()
            if joined:
                sections.append({"title": current_title, "content": joined})
            current_content = []

        tags = [
            "h1", "h2", "h3", "h4",
            "p", "ul", "ol", "table", "pre", "blockquote",
            # Confluence storage format macros
            "ac:structured-macro",
        ]

        for tag in soup.find_all(tags):
            name = (tag.name or "").lower()

            if name in {"h1", "h2", "h3", "h4"}:
                _flush()
                level = int(name[1])
                title = tag.get_text(" ", strip=True)
                if title:
                    heading_stack[level] = title
                    # Clear deeper headings when a higher-level heading appears.
                    for deeper in (4, 3, 2, 1):
                        if deeper > level and deeper in heading_stack:
                            del heading_stack[deeper]
                current_title = _heading_path()
                continue

            text = self._extract_tag_text(tag)
            if text:
                current_content.append(text)

        _flush()

        # Filter very short noise blocks.
        result = [s for s in sections if len((s.get("content") or "").strip()) > 40]
        log.debug("confluence.parser.sections", count=len(result))
        return result

    def _extract_tag_text(self, tag) -> str:
        """Extract text từ tag giữ nguyên cấu trúc list/table."""
        # Confluence macro blocks (storage format).
        if (tag.name or "").lower() == "ac:structured-macro":
            return self._extract_macro_text(tag)

        if tag.name in ["ul", "ol"]:
            items = []
            for li in tag.find_all("li"):
                text = li.get_text(" ", strip=True)
                if text:
                    items.append(f"- {text}")
            return "\n".join(items)

        if tag.name == "table":
            rows = []
            for row in tag.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if any(cells):
                    rows.append(" | ".join(cells))
            return "\n".join(rows)

        if tag.name == "pre":
            text = tag.get_text("\n", strip=True)
            if not text:
                return ""
            return f"```\\n{text}\\n```"

        if tag.name == "blockquote":
            text = tag.get_text(" ", strip=True)
            return f"> {text}" if text else ""

        return tag.get_text(" ", strip=True)

    def _extract_macro_text(self, tag) -> str:
        """
        Extract a reasonable plain-text representation for common Confluence macros.
        We keep it lightweight to avoid overfitting to any one Confluence variant.
        """
        name = tag.get("ac:name") or tag.get("name") or ""
        macro = str(name).strip().lower()

        # Code macro: keep the plain text body as a fenced block.
        if macro == "code":
            language = ""
            for param in tag.find_all("ac:parameter"):
                if (param.get("ac:name") or "").strip().lower() == "language":
                    language = param.get_text(" ", strip=True)
                    break
            body = tag.find("ac:plain-text-body") or tag.find("ac:rich-text-body")
            text = body.get_text("\n", strip=True) if body else tag.get_text("\n", strip=True)
            text = (text or "").strip()
            if not text:
                return ""
            lang_hint = language.strip() if language else ""
            return f"```{lang_hint}\\n{text}\\n```"

        # Info/panel/tip/warning/note macro: flatten text.
        if macro in {"info", "panel", "tip", "warning", "note"}:
            title = ""
            for param in tag.find_all("ac:parameter"):
                if (param.get("ac:name") or "").strip().lower() in {"title", "header"}:
                    title = param.get_text(" ", strip=True)
                    break
            body = tag.find("ac:rich-text-body") or tag.find("ac:plain-text-body")
            text = body.get_text(" ", strip=True) if body else tag.get_text(" ", strip=True)
            text = (text or "").strip()
            if not text:
                return ""
            prefix = macro.upper()
            if title:
                return f"{prefix} ({title}): {text}"
            return f"{prefix}: {text}"

        # Default: best-effort flatten.
        text = tag.get_text(" ", strip=True)
        return (text or "").strip()

    def _extract_structured(self, soup) -> str:
        """Extract toàn bộ text theo thứ tự DOM."""
        parts = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table", "pre", "blockquote", "ac:structured-macro"]):
            text = self._extract_tag_text(tag)
            if text:
                parts.append(text)
        return "\n\n".join(parts)
