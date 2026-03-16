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
                  (id, doc_type, title, content, source_document_ids, source_snapshot, question, answer, created_by, status, created_at, updated_at)
                VALUES
                  (CAST(:id AS UUID), :doc_type, :title, :content, CAST(:doc_ids AS JSON), CAST(:snapshot AS JSON), :question, :answer, :created_by, 'draft', :created_at, :updated_at)
                """
            ),
            {
                "id": draft_id,
                "doc_type": (doc_type or "srs").strip().lower(),
                "title": (title or "").strip() or "Draft",
                "content": content or "",
                "doc_ids": json.dumps(source_document_ids or []),
                "snapshot": json.dumps(source_snapshot or {}),
                "question": question,
                "answer": answer,
                "created_by": (created_by or "").strip() or None,
                "created_at": now,
                "updated_at": now,
            },
        )
        await self._session.commit()
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
        for k in ("source_document_ids", "source_snapshot"):
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
        await self._session.commit()
        return await self.get(draft_id)

