from models.document import Document, Chunk
from ingestion.cleaner import TextCleaner
from ingestion.chunker import TextChunker
from ingestion.metadata_extractor import MetadataExtractor
from indexing.vector_index import VectorIndex
from indexing.keyword_index import KeywordIndex
from persistence.document_repository import DocumentRepository
from connectors.base.base_connector import BaseConnector
import structlog

log = structlog.get_logger()


class IngestionPipeline:
    def __init__(self, session):
        self._session = session
        self._cleaner = TextCleaner()
        self._chunker = TextChunker()
        self._metadata = MetadataExtractor()
        self._vector_index = VectorIndex(session)
        self._keyword_index = KeywordIndex(session)
        self._repo = DocumentRepository(session)

    async def run(self, connector: BaseConnector) -> dict:
        stats = {"fetched": 0, "indexed": 0, "skipped": 0, "errors": 0}
        log.info("ingestion.start", connector=connector.__class__.__name__)

        documents = await connector.fetch_documents()
        stats["fetched"] = len(documents)

        for doc in documents:
            try:
                await self._process(doc)
                stats["indexed"] += 1
            except Exception as e:
                log.error("ingestion.doc.error", doc_id=doc.id, error=str(e))
                stats["errors"] += 1

        log.info("ingestion.done", **stats)
        return stats

    async def _process(self, doc: Document) -> None:
        doc.content = self._cleaner.clean(doc.content)
        if not doc.content:
            return

        doc.metadata = self._metadata.extract(doc)
        await self._repo.upsert(doc)

        chunks: list[Chunk] = self._chunker.chunk(doc.id, doc.content)
        await self._vector_index.index_chunks(chunks)
        await self._keyword_index.index_chunks(chunks)

        log.info("ingestion.doc.done", doc_id=doc.id, chunks=len(chunks))