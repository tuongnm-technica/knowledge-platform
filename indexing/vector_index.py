from models.document import Chunk
from storage.vector.vector_store import VectorStore
from utils.embeddings import get_embeddings_batch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

log = structlog.get_logger()

_vector_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


class VectorIndex:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._store = _get_store()

    async def index_chunks(self, chunks: list[Chunk], source="", title="") -> None:
        if not chunks:
            return

        texts = [c.content for c in chunks]
        log.info("vector_index.embedding", count=len(texts))
        vectors = await get_embeddings_batch(texts)

        for chunk in chunks:
            try:
                await self._session.execute(
                    text("""
                        INSERT INTO chunks (id, document_id, content, chunk_index)
                        VALUES (:id, :document_id, :content, :chunk_index)
                        ON CONFLICT (id) DO UPDATE
                          SET content = EXCLUDED.content
                    """),
                    {
                        "id": chunk.id,
                        "document_id": chunk.document_id,
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                    },
                )
            except Exception as e:
                log.error("vector_index.pg.error", chunk_id=chunk.id, error=str(e))

        await self._session.commit()

        for chunk, vector in zip(chunks, vectors):
            try:
                self._store.upsert(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    vector=vector,
                    content=chunk.content,
                    source=source, 
                    title=title,
                )
            except Exception as e:
                log.error("vector_index.qdrant.error", chunk_id=chunk.id, error=str(e))

        log.info("vector_index.done", indexed=len(chunks))