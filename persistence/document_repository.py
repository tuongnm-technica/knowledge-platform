import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import Document


def _pretty_group_name(group_id: str) -> str:
    gid = (group_id or "").strip()
    if not gid:
        return "Scope"
    gid = gid.removeprefix("group_")
    gid = gid.replace("__", "_")
    parts = [p for p in gid.split("_") if p]
    if not parts:
        return "Scope"

    # Common prefixes -> nicer display.
    if parts[:2] == ["confluence", "space"] and len(parts) >= 3:
        return f"Confluence space: {parts[2].upper()}"
    if parts[:2] == ["jira", "project"] and len(parts) >= 3:
        return f"Jira project: {parts[2].upper()}"
    if parts[:2] == ["slack", "channel"] and len(parts) >= 3:
        return f"Slack channel: {parts[2]}"
    if parts[:2] == ["file", "folder"] and len(parts) >= 3:
        return f"File folder: {parts[2]}"

    # Generic fallback: title-case tokens.
    label = " ".join(parts[:6]).strip()
    label = re.sub(r"\s+", " ", label)
    return label.title() if label else "Scope"


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert(self, doc: Document) -> str:
        """
        Upsert by (source, source_id) and return the canonical document id.

        Important: connectors may generate a random UUID for doc.id on each fetch.
        When a conflict happens, Postgres keeps the existing row id, so we must
        return it to keep downstream FK writes (chunks/graph) consistent.
        """
        permissions = [str(p).strip() for p in (doc.permissions or []) if str(p).strip()]

        result = await self._session.execute(
            text(
                """
                INSERT INTO documents
                (id, source, source_id, title, content, url, author,
                 created_at, updated_at, metadata, permissions, entities, workspace_id, summary)
                VALUES
                (:id, :source, :source_id, :title, :content, :url, :author,
                 :created_at, :updated_at, CAST(:metadata AS JSON), :permissions, :entities, :workspace_id, :summary)
                ON CONFLICT (source, source_id)
                DO UPDATE SET
                    title        = EXCLUDED.title,
                    content      = EXCLUDED.content,
                    url          = EXCLUDED.url,
                    author       = EXCLUDED.author,
                    updated_at   = EXCLUDED.updated_at,
                    metadata     = EXCLUDED.metadata,
                    permissions  = EXCLUDED.permissions,
                    entities     = EXCLUDED.entities,
                    workspace_id = EXCLUDED.workspace_id,
                    summary      = EXCLUDED.summary
                RETURNING id::text
                """
            ),
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
                "metadata": json.dumps(doc.metadata),
                "permissions": permissions,
                "entities": doc.entities,
                "workspace_id": doc.workspace_id,
                "summary": doc.summary,
            },
        )
        doc_id = result.scalar()
        canonical_id = str(doc_id) if doc_id else str(doc.id)

        # Permission-aware retrieval: sync ACL into document_permissions join table.
        # This must happen at ingestion time so retrieval can filter at query-time.
        if permissions:
            for group_id in sorted(set(permissions)):
                await self._session.execute(
                    text(
                        """
                        INSERT INTO groups (id, name)
                        VALUES (:id, :name)
                        ON CONFLICT (id) DO NOTHING
                        """
                    ),
                    {"id": group_id, "name": _pretty_group_name(group_id)},
                )

            await self._session.execute(
                text("DELETE FROM document_permissions WHERE document_id::text = :doc_id"),
                {"doc_id": canonical_id},
            )
            for group_id in sorted(set(permissions)):
                await self._session.execute(
                    text(
                        """
                        INSERT INTO document_permissions (document_id, group_id)
                        VALUES (CAST(:doc_id AS UUID), :group_id)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"doc_id": canonical_id, "group_id": group_id},
                )

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return canonical_id

    async def get_by_ids(self, doc_ids: list[str]) -> list[dict]:
        result = await self._session.execute(
            text("""
                SELECT
                    id::text,
                    title,
                    content,
                    url,
                    author,
                    updated_at,
                    source,
                    metadata,
                    permissions,
                    workspace_id,
                    summary
                FROM documents
                WHERE id::text = ANY(:ids)
            """),
            {"ids": doc_ids},
        )
        return [dict(row) for row in result.mappings().all()]

    async def list_documents(self, limit: int = 50, offset: int = 0, query: str | None = None) -> list[dict]:
        where_clause = ""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            where_clause = "WHERE title ILIKE :q OR author ILIKE :q"
            params["q"] = f"%{query}%"

        result = await self._session.execute(
            text(f"""
                SELECT
                    id::text,
                    title,
                    source,
                    url,
                    author,
                    updated_at
                FROM documents
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def count_total(self, query: str | None = None) -> int:
        where_clause = ""
        params = {}
        if query:
            where_clause = "WHERE title ILIKE :q OR author ILIKE :q"
            params["q"] = f"%{query}%"

        result = await self._session.execute(
            text(f"SELECT COUNT(*) FROM documents {where_clause}"),
            params
        )
        return result.scalar() or 0

    async def list_accessible(self, user_groups: list[str]) -> list[str]:
        result = await self._session.execute(
            text("""
                SELECT id::text
                FROM documents
                WHERE permissions && :groups
            """),
            {"groups": user_groups},
        )
        return [row[0] for row in result.fetchall()]

    async def get_neighbor_chunks(self, chunk_id: str, window: int | None = None):
        result = await self._session.execute(
            text("""
                SELECT chunk_index, document_id
                FROM chunks
                WHERE id = :chunk_id
            """),
            {"chunk_id": chunk_id},
        )
        row = result.mappings().first()
        if not row:
            return []

        idx = row["chunk_index"]
        doc_id = row["document_id"]
        if window is None:
            if idx <= 2:
                window = 2
            elif idx >= 10:
                window = 2
            else:
                window = 1
        window = max(0, int(window))

        result = await self._session.execute(
            text("""
                SELECT content
                FROM chunks
                WHERE document_id = :doc_id
                AND chunk_index BETWEEN :start AND :end
                ORDER BY chunk_index
            """),
            {
                "doc_id": doc_id,
                "start": idx - window,
                "end": idx + window,
            },
        )
        return result.mappings().all()

    async def get_section_chunks(self, parent_chunk_id: str) -> list[dict]:
        """Kéo toàn vẹn không sót chữ nào thuộc về Parent Section dựa trên parent_chunk_id."""
        # Note: If parent_chunk_id is None, this will return empty.
        result = await self._session.execute(
            text("""
                SELECT content, chunk_index, section_title, level
                FROM chunks
                WHERE parent_chunk_id = :parent_id
                ORDER BY chunk_index
            """),
            {"parent_id": parent_chunk_id},
        )
        return result.mappings().all()
