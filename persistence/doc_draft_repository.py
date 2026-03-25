from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DocDraftRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        *,
        doc_type: str,
        title: str,
        content: str,
        structured_data: dict[str, Any] | None = None,
        source_document_ids: list[str],
        source_snapshot: dict[str, Any],
        created_by: str | None,
        question: str | None = None,
        answer: str | None = None,
    ) -> dict[str, Any]:
        draft_id = str(uuid.uuid4())
        now = datetime.utcnow()
        await self._session.execute(
            text(
                """
                INSERT INTO doc_drafts
                  (id, doc_type, title, content, structured_data, source_document_ids, source_snapshot, question, answer, created_by, status, created_at, updated_at)
                VALUES
                  (CAST(:id AS UUID), :doc_type, :title, :content, CAST(:structured_data AS JSON), CAST(:doc_ids AS JSON), CAST(:snapshot AS JSON), :question, :answer, :created_by, 'draft', :created_at, :updated_at)
                """
            ),
            {
                "id": draft_id,
                "doc_type": (doc_type or "srs").strip().lower(),
                "title": (title or "").strip() or "Draft",
                "content": content or "",
                "structured_data": json.dumps(structured_data or {}),
                "doc_ids": json.dumps(source_document_ids or []),
                "snapshot": json.dumps(source_snapshot or {}),
                "question": question,
                "answer": answer,
                "created_by": (created_by or "").strip() or None,
                "created_at": now,
                "updated_at": now,
            },
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return await self.get(draft_id)

    async def get(self, draft_id: str) -> dict[str, Any] | None:
        draft_id = str(draft_id or "").strip()
        if not draft_id:
            return None
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT
                      id::text AS id,
                      doc_type,
                      title,
                      content,
                      structured_data,
                      source_document_ids,
                      source_snapshot,
                      question,
                      answer,
                      created_by,
                      status,
                      created_at,
                      updated_at
                    FROM doc_drafts
                    WHERE id::text = :id
                    LIMIT 1
                    """
                ),
                {"id": draft_id},
            )
        ).mappings().first()
        if not row:
            return None
        out = dict(row)
        for k in ("structured_data", "source_document_ids", "source_snapshot"):
            if isinstance(out.get(k), str):
                try:
                    out[k] = json.loads(out[k]) if out[k] else ([] if k == "source_document_ids" else {})
                except Exception:
                    out[k] = ([] if k == "source_document_ids" else {})
        return out

    async def update(
        self,
        draft_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        structured_data: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        draft_id = str(draft_id or "").strip()
        if not draft_id:
            return None

        updates: dict[str, Any] = {"id": draft_id, "updated_at": datetime.utcnow()}
        sets: list[str] = ["updated_at = :updated_at"]
        if title is not None:
            updates["title"] = (title or "").strip() or "Draft"
            sets.append("title = :title")
        if content is not None:
            updates["content"] = content or ""
            sets.append("content = :content")
        if structured_data is not None:
            updates["structured_data"] = json.dumps(structured_data)
            sets.append("structured_data = CAST(:structured_data AS JSON)")
        if status is not None:
            updates["status"] = (status or "").strip().lower()
            sets.append("status = :status")

        await self._session.execute(
            text(
                f"""
                UPDATE doc_drafts
                SET {", ".join(sets)}
                WHERE id::text = :id
                """
            ),
            updates,
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return await self.get(draft_id)

    async def list_recent(
        self,
        *,
        created_by: str | None,
        limit: int = 50,
        doc_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        created_by = (created_by or "").strip() or None
        doc_type = (doc_type or "").strip().lower() or None
        status = (status or "").strip().lower() or None

        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if created_by is not None:
            where.append("created_by = :created_by")
            params["created_by"] = created_by
        if doc_type is not None:
            where.append("doc_type = :doc_type")
            params["doc_type"] = doc_type
        if status is not None:
            where.append("status = :status")
            params["status"] = status
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        rows = (
            await self._session.execute(
                text(
                    f"""
                    SELECT
                      id::text AS id,
                      doc_type,
                      title,
                      created_by,
                      status,
                      created_at,
                      updated_at,
                      structured_data,
                      source_document_ids,
                      source_snapshot
                    FROM doc_drafts
                    {where_sql}
                    ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).mappings().all()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            for k in ("structured_data", "source_document_ids", "source_snapshot"):
                if isinstance(item.get(k), str):
                    try:
                        item[k] = json.loads(item[k]) if item[k] else ([] if k == "source_document_ids" else {})
                    except Exception:
                        item[k] = ([] if k == "source_document_ids" else {})
            out.append(item)
        return out

    async def delete(
        self,
        draft_id: str,
        *,
        created_by: str | None = None,
        allow_any: bool = False,
    ) -> bool:
        draft_id = str(draft_id or "").strip()
        if not draft_id:
            return False

        params: dict[str, Any] = {"id": draft_id}
        where = "id::text = :id"
        if not allow_any:
            created_by = (created_by or "").strip() or None
            if created_by is None:
                return False
            where += " AND created_by = :created_by"
            params["created_by"] = created_by

        res = await self._session.execute(
            text(f"DELETE FROM doc_drafts WHERE {where}"),
            params,
        )
        await self._session.commit()
        return bool(getattr(res, "rowcount", 0) or 0)
