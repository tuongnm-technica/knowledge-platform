from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ProjectMemoryRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert(
        self,
        *,
        memory_type: str,
        key: str,
        content: str,
        created_by: str | None = None,
    ) -> dict[str, Any] | None:
        memory_type = str(memory_type or "").strip().lower()
        key = str(key or "").strip()
        
        if not memory_type or not key:
            return None

        memory_id = str(uuid.uuid4())
        now = datetime.utcnow()
        created_by = str(created_by or "").strip() or None

        await self._session.execute(
            text(
                """
                INSERT INTO project_memories
                  (id, memory_type, key, content, created_by, created_at, updated_at)
                VALUES
                  (CAST(:id AS UUID), :memory_type, :key, :content, :created_by, :created_at, :updated_at)
                ON CONFLICT (memory_type, key)
                DO UPDATE SET
                  content = EXCLUDED.content,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": memory_id,
                "memory_type": memory_type,
                "key": key,
                "content": content or "",
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            },
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return await self.get(memory_type, key)

    async def get(self, memory_type: str, key: str) -> dict[str, Any] | None:
        memory_type = str(memory_type or "").strip().lower()
        key = str(key or "").strip()
        if not memory_type or not key:
            return None
            
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT id::text AS id, memory_type, key, content, created_by, created_at, updated_at
                    FROM project_memories
                    WHERE memory_type = :memory_type AND key = :key
                    LIMIT 1
                    """
                ),
                {"memory_type": memory_type, "key": key},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def get_all_grouped(self) -> dict[str, list[dict[str, Any]]]:
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT id::text AS id, memory_type, key, content, created_by, created_at, updated_at
                    FROM project_memories
                    ORDER BY memory_type ASC, key ASC
                    """
                )
            )
        ).mappings().all()
        
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            mtype = r["memory_type"]
            if mtype not in grouped:
                grouped[mtype] = []
            grouped[mtype].append(dict(r))
            
        return grouped

    async def delete(self, memory_id: str) -> bool:
        memory_id = str(memory_id or "").strip()
        if not memory_id:
            return False
        result = await self._session.execute(
            text("DELETE FROM project_memories WHERE id = CAST(:id AS UUID)"),
            {"id": memory_id},
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0
