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
                JOIN user_groups ug
                  ON ug.group_id = dp.group_id
                 AND ug.user_id = :user_id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM user_group_overrides ugo
                    WHERE ugo.user_id = ug.user_id
                      AND ugo.group_id = ug.group_id
                      AND COALESCE(ugo.effect, 'deny') = 'deny'
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM user_document_overrides udo
                    WHERE udo.user_id = :user_id
                      AND udo.document_id = dp.document_id
                      AND COALESCE(udo.effect, 'deny') = 'deny'
                )
            """),
            {"user_id": user_id},
        )
        return list(result.scalars().all())
