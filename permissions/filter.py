from permissions.acl import ACLFilter
from sqlalchemy.ext.asyncio import AsyncSession


class PermissionFilter:
    def __init__(self, session: AsyncSession):
        self._acl = ACLFilter(session)

    async def allowed_docs(self, user_id: str) -> list[str]:
        return await self._acl.get_allowed_document_ids(user_id)

    def filter_results(self, results: list[dict], allowed_ids: list[str]) -> list[dict]:
        allowed_set = set(str(i) for i in allowed_ids)
        return [r for r in results if str(r.get("document_id", "")) in allowed_set]