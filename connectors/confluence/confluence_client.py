from atlassian import Confluence
from config.settings import settings
import structlog

log = structlog.get_logger()


class ConfluenceClient:
    def __init__(self):
        if not all([settings.CONFLUENCE_URL, settings.CONFLUENCE_API_TOKEN]):
            raise ValueError("CONFLUENCE_URL, CONFLUENCE_API_TOKEN chưa được cấu hình")

        # Confluence Server — dùng Personal Access Token, không cần username
        self._client = Confluence(
            url=settings.CONFLUENCE_URL,
            token=settings.CONFLUENCE_API_TOKEN,  # ← dùng token= thay vì username/password
            cloud=False,
            timeout=180,
        )

    def get_spaces(self) -> list[dict]:
        try:
            result = self._client.get_all_spaces(start=0, limit=50)
            return result.get("results", [])
        except Exception as e:
            log.error("confluence.get_spaces.failed", error=str(e))
            return []

    def get_pages(self, space_key: str, limit: int = 100) -> list[dict]:
        try:
            return self._client.get_all_pages_from_space(
                space_key, start=0, limit=limit, expand="version,history"
            )
        except Exception as e:
            log.error("confluence.get_pages.failed", space=space_key, error=str(e))
            return []

    def get_page_body(self, page_id: str) -> str:
        try:
            page = self._client.get_page_by_id(page_id, expand="body.storage")
            return page["body"]["storage"]["value"]
        except Exception as e:
            log.error("confluence.get_body.failed", page_id=page_id, error=str(e))
            return ""

    def get_page_restrictions(self, page_id: str) -> list[dict]:
        try:
            result = self._client.get_all_restrictions_for_content(page_id)
            return result if isinstance(result, list) else []
        except Exception as e:
            log.error("confluence.get_restrictions.failed", error=str(e))
            return []

    def test_connection(self) -> bool:
        try:
            self._client.get_all_spaces(start=0, limit=1)
            return True
        except Exception as e:
            log.error("confluence.test_connection.failed", error=str(e))
            return False