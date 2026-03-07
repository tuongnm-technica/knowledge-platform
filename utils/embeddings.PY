from config.settings import settings
import structlog

log = structlog.get_logger()

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("embedding.model.loading", model=settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        log.info("embedding.model.ready")
    return _model


def get_embedding_sync(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.tolist()


async def get_embedding(text: str) -> list[float]:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_embedding_sync, text)


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]