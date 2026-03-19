from models.document import Chunk
from storage.vector.vector_store import VectorStore
from services.embedding_service import get_embedding_service
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
        self._embedding_service = get_embedding_service()

    async def index_chunks(self, chunks: list[Chunk], source="", title="") -> None:
        if not chunks:
            return

        texts = [c.content for c in chunks]
        log.info("vector_index.embedding", count=len(texts))
        try:
            vectors = await self._embedding_service.get_embeddings_batch(texts)
        except Exception as e:
            log.error("vector_index.embedding_failed", error=str(e))
            return

        # Replace strategy: remove existing chunks for this document only after embeddings are ready.
        document_id = chunks[0].document_id
        try:
            await self._session.execute(
                text("DELETE FROM chunks WHERE document_id = :document_id"),
                {"document_id": document_id},
            )
            await self._session.commit()
        except Exception as e:
            log.error("vector_index.pg.delete_failed", document_id=document_id, error=str(e))

        try:
            self._store.delete_by_document(document_id)
        except Exception as e:
            log.error("vector_index.qdrant.delete_failed", document_id=document_id, error=str(e))

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

        # Tối ưu hóa: Đẩy dữ liệu lên Qdrant theo Batch thay vì từng Point một (N+1 Problem)
        batch_data = []
        for chunk, vector in zip(chunks, vectors):
            batch_data.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "vector": vector,
                "content": chunk.content,
                "source": source,
                "title": title
            })
            
        try:
            # Gửi 1 lần duy nhất
            self._store.upsert_batch(batch_data)
        except Exception as e:
            log.error("vector_index.qdrant.batch_error", document_id=document_id, error=str(e))
            # Có thể throw exception ra ngoài để worker Retry lại cả job

        log.info("vector_index.done", indexed=len(chunks))
