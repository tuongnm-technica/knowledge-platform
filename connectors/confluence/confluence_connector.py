import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.confluence.confluence_client import ConfluenceClient
from connectors.confluence.confluence_parser import ConfluenceParser
from connectors.confluence.confluence_permissions import ConfluencePermissions
from config.settings import settings
import structlog

log = structlog.get_logger()

# ─── Chỉ sync những spaces này ────────────────────────────────────────────────
ALLOWED_SPACE_KEYS = [
    "EEP2",   # ECOS
    # "AIK",  # Thêm space khác vào đây
]


class ConfluenceConnector(BaseConnector):

    def __init__(self):
        self.validate_config()
        self._client = ConfluenceClient()
        self._parser = ConfluenceParser()
        self._permissions = ConfluencePermissions(self._client)

    def validate_config(self) -> bool:
        # Bỏ CONFLUENCE_USERNAME — Server dùng token là đủ
        if not all([settings.CONFLUENCE_URL, settings.CONFLUENCE_API_TOKEN]):
            raise ValueError("CONFLUENCE_URL và CONFLUENCE_API_TOKEN chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []

        all_spaces = self._client.get_spaces()
        # Lọc chỉ sync spaces trong whitelist
        spaces = [s for s in all_spaces if s["key"] in ALLOWED_SPACE_KEYS]
        log.info("confluence.fetch.start", total=len(all_spaces), syncing=len(spaces))

        for space in spaces:
            space_key = space["key"]
            space_name = space.get("name", space_key)
            log.info("confluence.fetch.space", space=space_key, name=space_name)

            pages = self._client.get_pages(space_key, limit=200)
            log.info("confluence.fetch.pages", space=space_key, count=len(pages))

            for page in pages:
                try:
                    page_id = page["id"]
                    body_html = self._client.get_page_body(page_id)
                    content = self._parser.parse(body_html)

                    if not content or len(content) < 20:
                        continue

                    permissions = self._permissions.get_permitted_groups(page_id, space_key)

                    created_at = self._parse_dt(page.get("history", {}).get("createdDate", ""))
                    updated_at = self._parse_dt(page.get("version", {}).get("when", ""))

                    doc = Document(
                        id=str(uuid.uuid4()),
                        source=SourceType.CONFLUENCE,
                        source_id=page_id,
                        title=page.get("title", "Untitled"),
                        content=content,
                        url=f"{settings.CONFLUENCE_URL.rstrip('/')}/wiki{page.get('_links', {}).get('webui', '')}",
                        author=page.get("history", {}).get("createdBy", {}).get("displayName", "unknown"),
                        created_at=created_at,
                        updated_at=updated_at,
                        metadata={
                            "space_key": space_key,
                            "space_name": space_name,
                            "page_id": page_id,
                        },
                        permissions=permissions,
                    )
                    documents.append(doc)
                    log.info("confluence.page.ok", title=page.get("title", "")[:60])

                except Exception as e:
                    log.error("confluence.page.error", page_id=page.get("id"), error=str(e))
                    continue  # Lỗi 1 page không crash toàn bộ

        log.info("confluence.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        return self._permissions.get_permitted_groups(source_id, "")

    @staticmethod
    def _parse_dt(s: str) -> datetime:
        if not s:
            return datetime.utcnow().replace(tzinfo=None)
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            # Bỏ timezone info để đồng nhất với PostgreSQL
            return dt.replace(tzinfo=None)
        except Exception:
            return datetime.utcnow().replace(tzinfo=None)