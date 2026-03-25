from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


log = structlog.get_logger()


class SyncRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_last_sync(self, connector: str) -> datetime | None:
        """Lấy thời điểm sync thành công gần nhất của connector."""
        result = await self._session.execute(
            text(
                """
                SELECT last_sync_at FROM sync_logs
                WHERE connector = :connector AND status IN ('success', 'partial')
                ORDER BY last_sync_at DESC
                LIMIT 1
                """
            ),
            {"connector": connector},
        )
        row = result.fetchone()
        return row[0] if row else None

    async def start_sync(self, connector: str) -> int:
        """Ghi log bắt đầu sync, trả về id."""
        result = await self._session.execute(
            text(
                """
                INSERT INTO sync_logs (connector, status, started_at, last_sync_at)
                VALUES (:connector, 'running', NOW(), NOW())
                RETURNING id
                """
            ),
            {"connector": connector},
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return int(result.scalar() or 0)

    async def update_progress(
        self,
        log_id: int,
        *,
        fetched: int | None = None,
        indexed: int | None = None,
        errors: int | None = None,
    ) -> bool:
        """
        Update running sync progress for UI progress bars.

        Notes:
        - Best-effort; only updates rows still in status='running'.
        - Uses NOW() for last_sync_at as a heartbeat timestamp while syncing.
        """
        sets: list[str] = ["last_sync_at = NOW()"]
        params: dict = {"id": int(log_id)}
        if fetched is not None:
            sets.append("fetched = :fetched")
            params["fetched"] = int(fetched)
        if indexed is not None:
            sets.append("indexed = :indexed")
            params["indexed"] = int(indexed)
        if errors is not None:
            sets.append("errors = :errors")
            params["errors"] = int(errors)

        if len(sets) == 1:
            return True

        result = await self._session.execute(
            text(
                f"""
                UPDATE sync_logs
                SET {", ".join(sets)}
                WHERE id = :id AND status = 'running'
                """
            ),
            params,
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return result.rowcount > 0

    async def finish_sync(
        self,
        log_id: int,
        fetched: int,
        indexed: int,
        errors: int,
        status: str = "success",
    ) -> None:
        """Cập nhật kết quả sau khi sync xong."""
        await self._session.execute(
            text(
                """
                UPDATE sync_logs
                SET status       = :status,
                    fetched      = :fetched,
                    indexed      = :indexed,
                    errors       = :errors,
                    last_sync_at = NOW(),
                    finished_at  = NOW()
                WHERE id = :id
                """
            ),
            {"id": int(log_id), "status": status, "fetched": int(fetched), "indexed": int(indexed), "errors": int(errors)},
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def get_stats(self, connector: str) -> dict:
        """Lấy thống kê sync gần nhất của connector."""
        result = await self._session.execute(
            text(
                """
                SELECT status, fetched, indexed, errors, last_sync_at, finished_at
                FROM sync_logs
                WHERE connector = :connector
                ORDER BY last_sync_at DESC
                LIMIT 1
                """
            ),
            {"connector": connector},
        )
        row = result.fetchone()
        if not row:
            return {"status": "never", "last_sync_at": None, "fetched": 0, "indexed": 0, "errors": 0}
        return {
            "status": row[0],
            "fetched": row[1] or 0,
            "indexed": row[2] or 0,
            "errors": row[3] or 0,
            "last_sync_at": row[4].strftime("%d/%m/%Y %H:%M") if row[4] else None,
        }

