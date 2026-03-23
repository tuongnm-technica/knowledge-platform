import uuid

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    VectorParams,
    FilterSelector,
)

from config.settings import settings


log = structlog.get_logger()
_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        kwargs = {
            "host": settings.QDRANT_HOST,
            "port": settings.QDRANT_PORT,
            "timeout": 30,
            "https": False,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
            kwargs["https"] = True
        _client = QdrantClient(**kwargs)
        log.info("qdrant.client.ready", host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


def get_qdrant() -> QdrantClient:
    return get_qdrant_client()


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

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False

    def upsert(
        self,
        chunk_id: str,
        document_id: str,
        vector: list[float],
        content: str,
        source: str = "",
        title: str = "",
    ) -> None:
        point = PointStruct(
            id=str(uuid.UUID(chunk_id)) if self._is_uuid(chunk_id) else abs(hash(chunk_id)) % (2**63),
            vector=vector,
            payload={
                "chunk_id": str(chunk_id),
                "document_id": str(document_id),
                "content": content,
                "source": source,
                "title": title,
            },
        )
        self._client.upsert(collection_name=settings.QDRANT_COLLECTION, points=[point])

    def upsert_batch(self, chunks_data: list[dict]) -> None:
        """
        Upsert nhiều vector cùng lúc để tối ưu hiệu năng mạng.
        chunks_data format: [{"chunk_id": str, "document_id": str, "vector": list, "content": str, "source": str, "title": str}]
        """
        if not chunks_data:
            return
            
        points = []
        for data in chunks_data:
            chunk_id = data["chunk_id"]
            points.append(
                PointStruct(
                    id=str(uuid.UUID(chunk_id)) if self._is_uuid(chunk_id) else abs(hash(chunk_id)) % (2**63),
                    vector=data["vector"],
                    payload={
                        "chunk_id": str(chunk_id),
                        "document_id": str(data["document_id"]),
                        "content": data["content"],
                        "source": data.get("source", ""),
                        "title": data.get("title", ""),
                    },
                )
            )
            
        # Đẩy toàn bộ lên Qdrant trong 1 network call duy nhất
        self._client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
        log.debug("qdrant.upsert_batch.done", count=len(points))

    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        allowed_document_ids: list[str] | None = None,
    ) -> list[dict]:
        query_filter = None
        if allowed_document_ids:
            str_ids = [str(did) for did in allowed_document_ids]
            query_filter = Filter(
                must=[FieldCondition(key="document_id", match=MatchAny(any=str_ids))]
            )

        hits = self._client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "chunk_id": payload.get("chunk_id", str(hit.id)),
                    "document_id": payload.get("document_id", ""),
                    "content": payload.get("content", ""),
                    "source": payload.get("source", ""),
                    "title": payload.get("title", ""),
                    "score": hit.score,
                    "vector_score": hit.score,
                    "keyword_score": 0.0,
                }
            )
        return results

    def delete_by_document(self, document_id: str) -> None:
        self._client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="document_id", match=MatchAny(any=[str(document_id)]))])
            ),
        )

    def delete_by_sources(self, sources: list[str]) -> None:
        if not sources:
            return
        self._client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="source", match=MatchAny(any=sources))])
            ),
        )


def recreate_collection(collection_name: str, *, size: int, distance: Distance = Distance.COSINE) -> None:
    client = get_qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if collection_name in existing:
        client.delete_collection(collection_name=collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=size, distance=distance),
    )
