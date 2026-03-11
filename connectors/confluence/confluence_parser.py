from bs4 import BeautifulSoup
import structlog

log = structlog.get_logger()


class ConfluenceParser:

    def parse(self, html_body: str) -> str:
        """Parse HTML thành plain text — dùng cho content chính."""
        if not html_body:
            return ""
        soup = BeautifulSoup(html_body, "html.parser")
        return self._extract_structured(soup)

    def parse_sections(self, html_body: str) -> list[dict]:
        """
        Parse HTML thành list sections theo cấu trúc heading.
        Mỗi section = {"title": ..., "content": ...}
        Dùng cho semantic chunking.
        """
        if not html_body:
            return []

        soup = BeautifulSoup(html_body, "html.parser")
        sections = []
        current_title = ""
        current_content = []

        for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table"]):
            if tag.name in ["h1", "h2", "h3", "h4"]:
                # Lưu section trước khi bắt đầu section mới
                if current_content:
                    sections.append({
                        "title":   current_title,
                        "content": "\n".join(current_content).strip(),
                    })
                current_title   = tag.get_text(strip=True)
                current_content = []
            else:
                text = self._extract_tag_text(tag)
                if text:
                    current_content.append(text)

        # Lưu section cuối
        if current_content:
            sections.append({
                "title":   current_title,
                "content": "\n".join(current_content).strip(),
            })

        # Lọc bỏ sections quá ngắn
        result = [s for s in sections if len(s["content"]) > 20]
        log.debug("confluence.parser.sections", count=len(result))
        return result

    def _extract_tag_text(self, tag) -> str:
        """Extract text từ tag giữ nguyên cấu trúc list/table."""
        if tag.name in ["ul", "ol"]:
            items = [f"- {li.get_text(strip=True)}" for li in tag.find_all("li")]
            return "\n".join(items)

        if tag.name == "table":
            rows = []
            for row in tag.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if any(cells):
                    rows.append(" | ".join(cells))
            return "\n".join(rows)

        return tag.get_text(strip=True)

    def _extract_structured(self, soup) -> str:
        """Extract toàn bộ text theo thứ tự DOM."""
        parts = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table"]):
            text = self._extract_tag_text(tag)
            if text:
                parts.append(text)
        return "\n\n".join(parts)