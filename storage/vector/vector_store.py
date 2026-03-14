from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance, VectorParams,
    PointStruct, Filter, FieldCondition, MatchAny,
    UpdateStatus,
)
from config.settings import settings
import structlog
import uuid

log = structlog.get_logger()

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        kwargs = dict(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=30)
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
            kwargs["https"] = True
        _client = QdrantClient(**kwargs)
        log.info("qdrant.client.ready", host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.VECTOR_DIM,
                distance=Distance.COSINE,
            ),
        )
        log.info("qdrant.collection.created", name=settings.QDRANT_COLLECTION)


class VectorStore:
    def __init__(self):
        self._client = get_qdrant_client()
        _ensure_collection(self._client)

    def upsert(
        self,
        chunk_id: str,
        document_id: str,
        vector: list[float],
        content: str,
        source: str = "",
        title: str = "",
    ) -> None:
        """Lưu vector + payload vào Qdrant. source và title dùng để filter sau."""
        point = PointStruct(
            id=str(uuid.UUID(chunk_id)) if self._is_uuid(chunk_id) else abs(hash(chunk_id)) % (2**63),
            vector=vector,
            payload={
                "chunk_id":    chunk_id,
                "document_id": document_id,
                "content":     content,
                "source":      source,   # ← thêm mới
                "title":       title,    # ← thêm mới
            },
        )
        self._client.upsert(collection_name=settings.QDRANT_COLLECTION, points=[point])

    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:
        query_filter = None
        if allowed_document_ids:
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchAny(any=allowed_document_ids))]
            )

        hits = self._client.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append({
                "chunk_id":      payload.get("chunk_id", str(hit.id)),
                "document_id":   payload.get("document_id", ""),
                "content":       payload.get("content", ""),
                "source":        payload.get("source", ""),   # ← đọc ra
                "title":         payload.get("title", ""),    # ← đọc ra
                "score":         hit.score,
                "vector_score":  hit.score,
                "keyword_score": 0.0,
            })
        return results

    def delete_by_document(self, document_id: str) -> None:
        from qdrant_client.http.models import FilterSelector
        self._client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="document_id", match=MatchAny(any=[document_id]))])
            ),
        )

    @staticmethod
    def _is_uuid(s: str) -> bool:
        try:
            uuid.UUID(s)
            return True
        except ValueError:
            return False
from qdrant_client import QdrantClient
from config.settings import settings

_qdrant = None


def get_qdrant():

    global _qdrant

    if _qdrant is None:

        _qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )

    return _qdrant