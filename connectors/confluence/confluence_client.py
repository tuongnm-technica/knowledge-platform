from atlassian import Confluence
from config.settings import settings
from datetime import datetime
import structlog
from urllib.parse import urljoin

import httpx

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
        username = (username or settings.CONFLUENCE_USERNAME or "").strip() or None
        cloud_flag = bool(getattr(settings, "CONFLUENCE_CLOUD", False))
        if cloud is not None:
            cloud_flag = bool(cloud)

        if not url or not token:
            raise ValueError("CONFLUENCE_URL va CONFLUENCE_API_TOKEN chua duoc cau hinh")
            raise ValueError("CONFLUENCE_URL và CONFLUENCE_API_TOKEN chưa được cấu hình")

        self._base_url = url.rstrip("/")
        self._token = token
        self._username = username
        self._auth_type = auth_type
        self._verify_tls = bool(getattr(settings, "CONFLUENCE_VERIFY_TLS", True))

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

    def _http(self) -> httpx.Client:
        headers = {"Accept": "application/json"}
        if self._auth_type == "basic" and self._username:
            return httpx.Client(timeout=60, verify=self._verify_tls, auth=(self._username, self._token), headers=headers)
        return httpx.Client(timeout=60, verify=self._verify_tls, headers={**headers, "Authorization": f"Bearer {self._token}"})

    def list_attachments(self, page_id: str, limit: int = 200) -> list[dict]:
        pid = str(page_id or "").strip()
        if not pid:
            return []
        url = f"{self._base_url}/rest/api/content/{pid}/child/attachment"
        try:
            with self._http() as client:
                resp = client.get(url, params={"limit": int(limit)})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("confluence.attachments.list_failed", page_id=pid, error=str(exc))
            return []

        results = data.get("results", []) if isinstance(data, dict) else []
        out: list[dict] = []
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("title") or "").strip()
            links = item.get("_links") or {}
            download = str(links.get("download") or "").strip() if isinstance(links, dict) else ""
            if not download:
                continue
            full = download if download.startswith("http") else urljoin(self._base_url + "/", download.lstrip("/"))

            meta = item.get("metadata") or {}
            mime_type = str(meta.get("mediaType") or meta.get("media_type") or "").strip() if isinstance(meta, dict) else ""

            file_size = None
            try:
                extensions = item.get("extensions") or {}
                if isinstance(extensions, dict):
                    file_size = int(extensions.get("fileSize") or 0) or None
            except Exception:
                file_size = None

            out.append({"filename": filename, "mime_type": mime_type, "download_url": full, "size": file_size})
        return out

    def download_attachment(self, download_url: str) -> bytes:
        href = str(download_url or "").strip()
        if not href:
            return b""
        try:
            with self._http() as client:
                resp = client.get(href, headers={"Accept": "*/*"})
                resp.raise_for_status()
                return resp.content or b""
        except Exception as exc:
            log.warning("confluence.attachments.download_failed", url=href, error=str(exc))
            return b""

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
