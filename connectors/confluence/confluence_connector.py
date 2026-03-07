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


class ConfluenceConnector(BaseConnector):
    def __init__(self):
        self.validate_config()
        self._client = ConfluenceClient()
        self._parser = ConfluenceParser()
        self._permissions = ConfluencePermissions(self._client)

    def validate_config(self) -> bool:
        if not all([settings.CONFLUENCE_URL, settings.CONFLUENCE_USERNAME, settings.CONFLUENCE_API_TOKEN]):
            raise ValueError("Confluence credentials chưa đầy đủ")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        spaces = self._client.get_spaces()

        for space in spaces:
            space_key = space["key"]
            log.info("confluence.fetch.space", space=space_key)
            pages = self._client.get_pages(space_key)

            for page in pages:
                page_id = page["id"]
                body_html = self._client.get_page_body(page_id)
                content = self._parser.parse(body_html)

                if not content or len(content) < 20:
                    continue

                permissions = self._permissions.get_permitted_groups(page_id, space_key)

                def parse_dt(s):
                    try:
                        return datetime.fromisoformat(s.replace("Z", "+00:00"))
                    except Exception:
                        return datetime.utcnow()

                created_str = page.get("history", {}).get("createdDate", "")
                updated_str = page.get("version", {}).get("when", "")

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.CONFLUENCE,
                    source_id=page_id,
                    title=page.get("title", "Untitled"),
                    content=content,
                    url=f"{settings.CONFLUENCE_URL}/wiki{page.get('_links', {}).get('webui', '')}",
                    author=page.get("history", {}).get("createdBy", {}).get("displayName", "unknown"),
                    created_at=parse_dt(created_str),
                    updated_at=parse_dt(updated_str),
                    metadata={"space_key": space_key, "page_id": page_id},
                    permissions=permissions,
                )
                documents.append(doc)

        log.info("confluence.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        return self._permissions.get_permitted_groups(source_id, "")