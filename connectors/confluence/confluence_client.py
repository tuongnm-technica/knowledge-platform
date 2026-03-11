from atlassian import Confluence
from config.settings import settings
from datetime import datetime
import structlog

log = structlog.get_logger()


class ConfluenceClient:
    def __init__(self):
        if not all([settings.CONFLUENCE_URL, settings.CONFLUENCE_API_TOKEN]):
            raise ValueError("CONFLUENCE_URL và CONFLUENCE_API_TOKEN chưa được cấu hình")

        self._client = Confluence(
            url=settings.CONFLUENCE_URL,
            token=settings.CONFLUENCE_API_TOKEN,
            cloud=False,
            timeout=120,
        )

    def get_spaces(self) -> list[dict]:
        try:
            result = self._client.get_all_spaces(start=0, limit=50)
            return result.get("results", [])
        except Exception as e:
            log.error("confluence.get_spaces.failed", error=str(e))
            return []

    def get_pages(self, space_key: str, limit: int = 500) -> list[dict]:
        """Full sync — lấy toàn bộ pages trong space."""
        try:
            return self._client.get_all_pages_from_space(
                space_key, start=0, limit=limit, expand="version,history"
            )
        except Exception as e:
            log.error("confluence.get_pages.failed", space=space_key, error=str(e))
            return []

    def get_pages_since(self, space_key: str, since: datetime, limit: int = 500) -> list[dict]:
        """
        Incremental sync — chỉ lấy pages được sửa SAU thời điểm since.
        Dùng Confluence CQL: lastModified > "yyyy-MM-dd HH:mm"
        """
        try:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            cql = (
                f'space = "{space_key}" '
                f'AND lastModified > "{since_str}" '
                f'ORDER BY lastModified ASC'
            )
            log.info("confluence.get_pages_since", space=space_key, since=since_str)
            result = self._client.cql(cql, limit=limit, expand="version,history")
            pages = result.get("results", [])

            # CQL wrap content — normalize về cùng format với get_pages
            normalized = [p.get("content", p) for p in pages]
            log.info("confluence.incremental.found", space=space_key, count=len(normalized))
            return normalized

        except Exception as e:
            log.error("confluence.get_pages_since.failed", space=space_key, error=str(e))
            log.warning("confluence.fallback_to_full_sync", space=space_key)
            return self.get_pages(space_key, limit=limit)

    def get_page_body(self, page_id: str) -> str:
        try:
            page = self._client.get_page_by_id(page_id, expand="body.storage")
            return page.get("body", {}).get("storage", {}).get("value", "")
        except Exception as e:
            log.error("confluence.get_page_body.failed", page_id=page_id, error=str(e))
            return ""

    def test_connection(self) -> bool:
        try:
            self._client.get_all_spaces(start=0, limit=1)
            return True
        except Exception as e:
            log.error("confluence.test_connection.failed", error=str(e))
            return False