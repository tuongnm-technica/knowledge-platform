from atlassian import Confluence
from config.settings import settings
from datetime import datetime
import structlog

log = structlog.get_logger()


class ConfluenceClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_token: str | None = None,
        username: str | None = None,
        auth_type: str | None = None,  # token|basic
        cloud: bool | None = None,
    ):
        url = (base_url or settings.CONFLUENCE_URL or "").strip()
        token = (api_token or settings.CONFLUENCE_API_TOKEN or "").strip()
        auth_type = (auth_type or "token").strip().lower()
        cloud_flag = bool(getattr(settings, "CONFLUENCE_CLOUD", False))
        if cloud is not None:
            cloud_flag = bool(cloud)

        if not url or not token:
            raise ValueError("CONFLUENCE_URL va CONFLUENCE_API_TOKEN chua duoc cau hinh")
            raise ValueError("CONFLUENCE_URL và CONFLUENCE_API_TOKEN chưa được cấu hình")

        if auth_type == "basic":
            user = (username or "").strip()
            if not user:
                raise ValueError("CONFLUENCE username/email is required for basic auth")
            self._client = Confluence(
                url=url,
                username=user,
                password=token,
                cloud=cloud_flag,
                timeout=120,
            )
        else:
            self._client = Confluence(
                url=url,
                token=token,
                cloud=cloud_flag,
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
            start = 0
            pages: list[dict] = []
            while True:
                batch = self._client.get_all_pages_from_space(
                    space_key,
                    start=start,
                    limit=limit,
                    expand="version,history,space",
                )
                if not batch:
                    break
                pages.extend(batch)
                if len(batch) < limit:
                    break
                start += limit
            return pages
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
                f'type = page AND space = "{space_key}" '
                f'AND lastModified > "{since_str}" '
                f'ORDER BY lastModified ASC'
            )
            log.info("confluence.get_pages_since", space=space_key, since=since_str)
            start = 0
            pages: list[dict] = []
            while True:
                result = self._client.cql(
                    cql,
                    start=start,
                    limit=limit,
                    expand="content.version,content.history,content.space",
                )
                batch = result.get("results", []) if isinstance(result, dict) else []
                if not batch:
                    break
                pages.extend(batch)
                if len(batch) < limit:
                    break
                start += limit

            # CQL wrap content — normalize về cùng format với get_pages
            normalized = [p.get("content", p) for p in pages if isinstance(p, dict)]
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

    def get_page_restrictions(self, page_id: str) -> list[dict]:
        """
        Best-effort page restriction lookup. Returns a normalized list of restriction entries.
        """
        try:
            data = self._client.get_page_restrictions(page_id)  # type: ignore[attr-defined]
        except Exception:
            data = None

        if not data:
            return []

        restrictions = []
        if isinstance(data, dict):
            for scope in ("read", "update"):
                items = (data.get(scope) or {}).get("restrictions") or []
                if isinstance(items, list):
                    restrictions.extend(items)
            if not restrictions and "results" in data and isinstance(data["results"], list):
                restrictions = data["results"]

        return [r for r in restrictions if isinstance(r, dict)]

    def test_connection(self) -> bool:
        try:
            self._client.get_all_spaces(start=0, limit=1)
            return True
        except Exception as e:
            log.error("confluence.test_connection.failed", error=str(e))
            return False
