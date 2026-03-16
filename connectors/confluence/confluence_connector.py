import uuid
from datetime import datetime
import asyncio
import re
from urllib.parse import quote_plus, urlparse

import structlog

from config.settings import settings
from connectors.base.base_connector import BaseConnector
from connectors.confluence.confluence_client import ConfluenceClient
from connectors.confluence.confluence_parser import ConfluenceParser
from connectors.confluence.confluence_permissions import ConfluencePermissions
from models.document import Document, SourceType
from permissions.workspace_config import get_confluence_workspace


log = structlog.get_logger()


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def _perm_to_group_id(permission: str) -> str:
    """
    Normalize connector permission ids into internal group ids.

    Examples:
    - confluence_space_ABC -> group_confluence_space_abc
    - confluence_group_My Team -> group_confluence_group_my_team
    """
    perm = str(permission or "").strip()
    if not perm:
        return ""
    if perm.startswith("group_"):
        return perm
    return f"group_{_slugify(perm)}"


def _confluence_ui_url(*, base_url: str, webui: str, space_key: str, page_id: str, title: str) -> str:
    """
    Build a user-facing Confluence UI URL.

    Real-world Confluence deployments vary:
    - Some serve UI at `/spaces/...` (no `/wiki` prefix)
    - Confluence Cloud usually serves UI under `/wiki/...`
    We prefer `_links.webui` when available because it matches the instance routing.
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ""

    webui = (webui or "").strip()
    if webui.startswith("http://") or webui.startswith("https://"):
        return webui

    parsed = urlparse(base)
    if parsed.scheme and parsed.netloc:
        origin = f"{parsed.scheme}://{parsed.netloc}"
        base_path = (parsed.path or "").rstrip("/")
    else:
        # If base_url is missing scheme, keep it as-is.
        origin = base
        base_path = ""

    if webui:
        if not webui.startswith("/"):
            webui = "/" + webui
        # Some Confluence deployments (notably cloud) serve UI under `/wiki` even if webui is `/spaces/...`.
        if base_path.lower().endswith("/wiki") and webui.startswith("/spaces/"):
            return origin + base_path + webui
        return origin + webui

    # Fallback: match common "pretty URL" format shown in the browser address bar.
    # Keep `/wiki` only if it was explicitly part of the configured base URL path.
    context = base_path if base_path.lower().endswith("/wiki") else ""
    title_slug = quote_plus((title or "").strip() or "Untitled")
    return f"{origin}{context}/spaces/{space_key}/pages/{page_id}/{title_slug}"


def _allowed_space_keys(override: set[str] | None = None) -> set[str]:
    if override:
        return {key.strip() for key in override if key and str(key).strip()}
    raw = (settings.CONFLUENCE_SPACE_KEYS or "").strip()
    if not raw:
        return set()
    return {key.strip() for key in raw.split(",") if key.strip()}


class ConfluenceConnector(BaseConnector):
    def __init__(
        self,
        *,
        space_keys: set[str] | None = None,
        base_url: str | None = None,
        username: str | None = None,
        api_token: str | None = None,
        auth_type: str | None = None,  # token|basic
    ):
        self._base_url = (base_url or settings.CONFLUENCE_URL or "").strip()
        self._api_token = (api_token or settings.CONFLUENCE_API_TOKEN or "").strip()
        self._username = (username or "").strip() or None
        self._auth_type = (auth_type or ("basic" if self._username else "token")).strip().lower()

        self.validate_config()
        self._client = ConfluenceClient(
            base_url=self._base_url,
            api_token=self._api_token,
            username=self._username,
            auth_type=self._auth_type,
        )
        self._parser = ConfluenceParser()
        self._permissions = ConfluencePermissions(self._client)
        self._space_keys = _allowed_space_keys(space_keys)

    def validate_config(self) -> bool:
        if not self._base_url or not self._api_token:
            raise ValueError("CONFLUENCE_URL va CONFLUENCE_API_TOKEN chua duoc cau hinh")
        if self._auth_type == "basic" and not self._username:
            raise ValueError("CONFLUENCE username/email is required for basic auth")
        return True

    async def fetch_documents(self, last_sync: datetime | None = None) -> list[Document]:
        documents: list[Document] = []
        all_spaces = await asyncio.to_thread(self._client.get_spaces)
        allowed_space_keys = self._space_keys
        spaces = [
            space for space in all_spaces
            if not allowed_space_keys or space["key"] in allowed_space_keys
        ]

        log.info("confluence.fetch.start", total=len(all_spaces), syncing=len(spaces))

        for space in spaces:
            space_key = space["key"]
            space_name = space.get("name", space_key)
            log.info("confluence.fetch.space", space=space_key, name=space_name)

            if last_sync:
                pages = await asyncio.to_thread(self._client.get_pages_since, space_key, last_sync, 200)
            else:
                pages = await asyncio.to_thread(self._client.get_pages, space_key, 200)
            log.info("confluence.fetch.pages", space=space_key, count=len(pages))

            sem = asyncio.Semaphore(6)

            async def _worker(page: dict) -> Document | None:
                async with sem:
                    try:
                        return await self._process_page(page, space_key, space_name)
                    except Exception as exc:
                        log.error("confluence.page.error", page_id=page.get("id"), error=str(exc))
                        return None

            # Process in small batches to avoid creating too many pending tasks for large spaces.
            batch_size = 40
            for start in range(0, len(pages), batch_size):
                slice_pages = pages[start : start + batch_size]
                batch = await asyncio.gather(*[_worker(page) for page in slice_pages])
                documents.extend([doc for doc in batch if doc])

        log.info("confluence.fetch.done", total=len(documents))
        return documents

    async def _process_page(self, page: dict, space_key: str, space_name: str) -> Document | None:
        page_id = page["id"]
        body_html = await asyncio.to_thread(self._client.get_page_body, page_id)
        content = self._parser.parse(body_html)

        if not content or len(content.strip()) < 20:
            return None

        # Collect image placeholders so ingestion can fetch + caption the assets later.
        img_files = re.findall(r"\[\[IMAGE:([^\]]+)\]\]", content or "")
        img_urls_raw = re.findall(r"\[\[IMAGE_URL:([^\]]+)\]\]", content or "")
        img_urls: list[dict] = []
        for raw in img_urls_raw:
            raw = str(raw or "").strip()
            if not raw:
                continue
            if "|" in raw:
                url, alt = raw.split("|", 1)
                img_urls.append({"url": url.strip(), "alt": alt.strip()})
            else:
                img_urls.append({"url": raw.strip(), "alt": ""})

        author_info = page.get("history", {}).get("createdBy", {})
        author = author_info.get("displayName", "unknown")
        web_ui = page.get("_links", {}).get("webui", "")

        # Use Confluence's own `webui` link to match the instance routing in real deployments.
        # Example (self-hosted): /spaces/AIK/pages/55607532/Some+Title
        # Example (cloud): /wiki/spaces/ABC/pages/123/Some+Title
        ui_url = _confluence_ui_url(
            base_url=self._base_url,
            webui=web_ui,
            space_key=str(space_key),
            page_id=str(page_id),
            title=str(page.get("title", "")),
        )

        raw_permissions = self._permissions.get_permitted_groups(str(page_id), str(space_key))
        permissions = sorted({gid for gid in (_perm_to_group_id(p) for p in raw_permissions) if gid})
        if not permissions:
            permissions = [_perm_to_group_id(f"confluence_space_{space_key}")]

        doc = Document(
            id=str(uuid.uuid4()),
            source=SourceType.CONFLUENCE,
            source_id=page_id,
            title=page.get("title", "Untitled"),
            content=content,
            url=ui_url,
            author=author,
            created_at=self._parse_dt(page.get("history", {}).get("createdDate", "")),
            updated_at=self._parse_dt(page.get("version", {}).get("when", "")),
            metadata={
                "space_key": space_key,
                "space_name": space_name,
                "page_id": page_id,
                "stable_url": ui_url,
                "webui": web_ui,
                "raw_html": body_html,
                "image_attachments": [{"filename": f.strip()} for f in img_files if str(f or "").strip()],
                "image_urls": img_urls,
                "author_name": author,
                "author_username": author_info.get("username", "") or author_info.get("name", ""),
                "author_email": author_info.get("email", "") or author_info.get("emailAddress", ""),
                "permission_id": _perm_to_group_id(f"confluence_space_{space_key}"),
            },
            permissions=permissions,
            workspace_id=get_confluence_workspace(space_key),
        )

        log.info("confluence.page.ok", page_id=page_id, title=doc.title[:60])
        return doc

    async def get_permissions(self, source_id: str) -> list[str]:
        return self._permissions.get_permitted_groups(source_id, "")

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        if not value:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return datetime.utcnow()
