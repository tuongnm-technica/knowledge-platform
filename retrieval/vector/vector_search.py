from storage.vector.vector_store import VectorStore
from utils.embeddings import get_embedding
import structlog

log = structlog.get_logger()

_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


class VectorSearch:
    def __init__(self, _session=None):
        self._store = _get_store()

    async def search(
        self,
        query: str,
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:
        embedding = await get_embedding(query)
        results = self._store.similarity_search(
            query_vector=embedding,
            top_k=top_k,
            allowed_document_ids=allowed_document_ids,
        )
        return results