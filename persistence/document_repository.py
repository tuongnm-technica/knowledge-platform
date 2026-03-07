from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert(self, doc: Document) -> None:
        await self._session.execute(
            text("""
                INSERT INTO documents
                  (id, source, source_id, title, content, url, author,
                   created_at, updated_at, metadata, permissions, entities)
                VALUES
                  (:id, :source, :source_id, :title, :content, :url, :author,
                   :created_at, :updated_at, :metadata::jsonb, :permissions, :entities)
                ON CONFLICT (source, source_id)
                DO UPDATE SET
                  title = EXCLUDED.title,
                  content = EXCLUDED.content,
                  url = EXCLUDED.url,
                  updated_at = EXCLUDED.updated_at,
                  metadata = EXCLUDED.metadata,
                  permissions = EXCLUDED.permissions
            """),
            {
                "id": doc.id,
                "source": doc.source.value,
                "source_id": doc.source_id,
                "title": doc.title,
                "content": doc.content,
                "url": doc.url,
                "author": doc.author,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "metadata": str(doc.metadata),
                "permissions": doc.permissions,
                "entities": doc.entities,
            },
        )
        await self._session.commit()

    async def get_by_ids(self, doc_ids: list[str]) -> list[dict]:
        result = await self._session.execute(
            text("""
                SELECT id::text, title, url, author, updated_at, source, metadata
                FROM documents WHERE id = ANY(:ids)
            """),
            {"ids": doc_ids},
        )
        return [dict(r) for r in result.mappings().all()]