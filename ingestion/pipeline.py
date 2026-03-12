import inspect
from datetime import datetime
from models.document import Document, SourceType
from ingestion.cleaner import TextCleaner
from ingestion.chunker import TextChunker
from ingestion.metadata_extractor import MetadataExtractor
from indexing.vector_index import VectorIndex
from indexing.keyword_index import KeywordIndex
from persistence.document_repository import DocumentRepository
from persistence.sync_repository import SyncRepository
from connectors.base.base_connector import BaseConnector
import structlog

log = structlog.get_logger()


class IngestionPipeline:

    def __init__(self, session):
        self._session       = session
        self._cleaner       = TextCleaner()
        self._chunker       = TextChunker()
        self._metadata      = MetadataExtractor()
        self._vector_index  = VectorIndex(session)
        self._keyword_index = KeywordIndex(session)
        self._repo          = DocumentRepository(session)
        self._sync_repo     = SyncRepository(session)

    async def run(self, connector: BaseConnector, incremental: bool = True) -> dict:
        stats          = {"fetched": 0, "indexed": 0, "skipped": 0, "errors": 0}
        connector_name = connector.__class__.__name__.replace("Connector", "").lower()

        last_sync = None
        if incremental:
            last_sync = await self._sync_repo.get_last_sync(connector_name)
            if last_sync:
                log.info("ingestion.incremental", connector=connector_name,
                         since=last_sync.isoformat())
            else:
                log.info("ingestion.first_run_full_sync", connector=connector_name)

        log_id = await self._sync_repo.start_sync(connector_name)
        log.info("ingestion.start", connector=connector_name,
                 incremental=incremental, last_sync=str(last_sync))

        try:
            sig = inspect.signature(connector.fetch_documents)
            if "last_sync" in sig.parameters:
                documents = await connector.fetch_documents(last_sync=last_sync)
            else:
                documents = await connector.fetch_documents()
        except Exception as e:
            log.error("ingestion.fetch.failed", error=str(e))
            await self._sync_repo.finish_sync(log_id, 0, 0, 1, status="failed")
            return stats

        stats["fetched"] = len(documents)

        for doc in documents:
            try:
                await self._process(doc)
                stats["indexed"] += 1
            except Exception as e:
                log.error("ingestion.doc.error", doc_id=doc.id, error=str(e))
                stats["errors"] += 1

        status = "success" if stats["errors"] == 0 else "partial"
        await self._sync_repo.finish_sync(
            log_id,
            fetched=stats["fetched"],
            indexed=stats["indexed"],
            errors=stats["errors"],
            status=status,
        )

        log.info("ingestion.done", connector=connector_name, **stats)
        return stats

    async def _process(self, doc: Document) -> None:
        # Confluence: extract sections TRƯỚC khi clean
        sections = None
        if doc.source == SourceType.CONFLUENCE:
            raw_html = doc.metadata.get("raw_html", "")
            if raw_html:
                from connectors.confluence.confluence_parser import ConfluenceParser
                sections = ConfluenceParser().parse_sections(raw_html)
                log.info("ingestion.sections", doc_id=doc.id, count=len(sections))

        # Clean content
        doc.content = self._cleaner.clean(doc.content)
        if not doc.content:
            log.debug("ingestion.skip.empty", doc_id=doc.id)
            return

        # Extract metadata
        doc.metadata = self._metadata.extract(doc)

        # Upsert document vào PostgreSQL
        await self._repo.upsert(doc)

        # ── Smart chunking theo source ────────────────────────────────────────
        chunks = self._smart_chunk(doc, sections)

        if not chunks:
            log.warning("ingestion.skip.no_chunks", doc_id=doc.id)
            return

        # Index vào Qdrant + PostgreSQL FTS
        await self._vector_index.index_chunks(chunks)
        await self._keyword_index.index_chunks(chunks)

        log.info("ingestion.doc.done", doc_id=doc.id,
                 source=doc.source.value, chunks=len(chunks))

    def _smart_chunk(self, doc: Document, sections=None) -> list:
        """Chọn chunking strategy phù hợp theo source"""

        # Confluence: semantic theo heading
        if sections:
            chunks = self._chunker.chunk_by_sections(doc.id, sections)
            log.info("ingestion.chunk.semantic", doc_id=doc.id, chunks=len(chunks))
            return chunks

        # Slack: theo conversation window
        if doc.source == SourceType.SLACK:
            chunks = self._chunker.chunk_slack(doc.id, doc.content)
            log.info("ingestion.chunk.slack", doc_id=doc.id, chunks=len(chunks))
            return chunks

        # Jira: theo section (summary + description)
        if doc.source == SourceType.JIRA:
            chunks = self._chunker.chunk_jira(doc.id, doc.content)
            log.info("ingestion.chunk.jira", doc_id=doc.id, chunks=len(chunks))
            return chunks

        # File Server: paragraph-aware
        if doc.source == SourceType.FILE_SERVER:
            chunks = self._chunker.chunk_file(doc.id, doc.content)
            log.info("ingestion.chunk.file", doc_id=doc.id, chunks=len(chunks))
            return chunks

        # Default: word-count
        chunks = self._chunker.chunk(doc.id, doc.content)
        log.info("ingestion.chunk.word", doc_id=doc.id, chunks=len(chunks))
        return chunks