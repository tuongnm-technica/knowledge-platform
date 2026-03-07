from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class ACLFilter:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_allowed_document_ids(self, user_id: str) -> list[str]:
        result = await self._session.execute(
            text("""
                SELECT DISTINCT dp.document_id::text
                FROM document_permissions dp
                JOIN user_groups ug ON ug.group_id = dp.group_id
                WHERE ug.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        return list(result.scalars().all())