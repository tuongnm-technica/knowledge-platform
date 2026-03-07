from sqlalchemy.ext.asyncio import AsyncSession
import structlog

log = structlog.get_logger()


class KeywordIndex:
    """
    PostgreSQL full-text search (GIN index on chunks.content).
    Index đã được tạo tự động trong create_tables().
    Không cần làm gì thêm ở đây.
    """
    def __init__(self, session: AsyncSession):
        self._session = session

    async def index_chunks(self, chunks) -> None:
        log.debug("keyword_index.ready", count=len(chunks))