from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class SummaryRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, document_id: str) -> str | None:
        result = await self._session.execute(
            text("SELECT summary FROM document_summaries WHERE document_id = :id"),
            {"id": document_id},
        )
        return result.scalar_one_or_none()

    async def save(self, document_id: str, summary: str) -> None:
        await self._session.execute(
            text("""
                INSERT INTO document_summaries (document_id, summary)
                VALUES (:id, :summary)
                ON CONFLICT (document_id) DO UPDATE SET summary = EXCLUDED.summary
            """),
            {"id": document_id, "summary": summary},
        )
        await self._session.commit()