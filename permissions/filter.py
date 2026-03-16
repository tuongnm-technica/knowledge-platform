from permissions.acl import ACLFilter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class PermissionFilter:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._acl = ACLFilter(session)

    async def allowed_docs(self, user_id: str) -> list[str] | None:
        """
        Return allowed document ids for a user.

        - Admin users: return None (meaning unrestricted).
        - Non-admin: return a list (can be empty, meaning no access).
        """
        try:
            r = await self._session.execute(
                text("SELECT is_admin FROM users WHERE id = :id"),
                {"id": user_id},
            )
            is_admin = bool(r.scalar() or False)
            if is_admin:
                return None
        except Exception:
            pass
        return await self._acl.get_allowed_document_ids(user_id)

    def filter_results(self, results: list[dict], allowed_ids: list[str]) -> list[dict]:
        allowed_set = set(str(i) for i in allowed_ids)
        return [r for r in results if str(r.get("document_id", "")) in allowed_set]
