from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

log = structlog.get_logger()


class SyncRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_last_sync(self, connector: str) -> datetime | None:
        """Lấy thời điểm sync thành công gần nhất của connector."""
        result = await self._session.execute(
            text("""
                SELECT last_sync_at FROM sync_logs
                WHERE connector = :connector AND status IN ('success', 'partial')
                ORDER BY last_sync_at DESC
                LIMIT 1
            """),
            {"connector": connector}
        )
        row = result.fetchone()
        return row[0] if row else None

    async def start_sync(self, connector: str) -> int:
        """Ghi log bắt đầu sync, trả về id."""
        result = await self._session.execute(
            text("""
                INSERT INTO sync_logs (connector, status, started_at, last_sync_at)
                VALUES (:connector, 'running', NOW(), NOW())
                RETURNING id
            """),
            {"connector": connector}
        )
        await self._session.commit()
        return result.scalar()

    async def finish_sync(self, log_id: int, fetched: int, indexed: int, errors: int, status: str = "success"):
        """Cập nhật kết quả sau khi sync xong."""
        await self._session.execute(
            text("""
                UPDATE sync_logs
                SET status       = :status,
                    fetched      = :fetched,
                    indexed      = :indexed,
                    errors       = :errors,
                    last_sync_at = NOW(),
                    finished_at  = NOW()
                WHERE id = :id
            """),
            {"id": log_id, "status": status, "fetched": fetched, "indexed": indexed, "errors": errors}
        )
        await self._session.commit()

    async def get_stats(self, connector: str) -> dict:
        """Lấy thống kê sync gần nhất của connector."""
        result = await self._session.execute(
            text("""
                SELECT status, fetched, indexed, errors, last_sync_at, finished_at
                FROM sync_logs
                WHERE connector = :connector
                ORDER BY last_sync_at DESC
                LIMIT 1
            """),
            {"connector": connector}
        )
        row = result.fetchone()
        if not row:
            return {"status": "never", "last_sync_at": None, "fetched": 0, "indexed": 0, "errors": 0}
        return {
            "status":       row[0],
            "fetched":      row[1] or 0,
            "indexed":      row[2] or 0,
            "errors":       row[3] or 0,
            "last_sync_at": row[4].strftime("%d/%m/%Y %H:%M") if row[4] else None,
        }