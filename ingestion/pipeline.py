import inspect
import time

import structlog

from connectors.base.base_connector import BaseConnector
from graph.entity_extractor import EntityExtractor
from graph.identity_resolver import IdentityResolver
from graph.document_linker import DocumentLinker
from graph.knowledge_graph import KnowledgeGraph
from indexing.keyword_index import KeywordIndex
from indexing.vector_index import VectorIndex
from ingestion.chunker import TextChunker
from ingestion.cleaner import TextCleaner
from ingestion.metadata_extractor import MetadataExtractor
from models.document import Document, SourceType
from persistence.document_repository import DocumentRepository
from persistence.sync_repository import SyncRepository


log = structlog.get_logger()


class IngestionPipeline:
    def __init__(self, session):
        self._session = session
        self._cleaner = TextCleaner()
        self._chunker = TextChunker()
        self._metadata = MetadataExtractor()
        self._entities = EntityExtractor()
        self._identities = IdentityResolver()
        self._vector_index = VectorIndex(session)
        self._keyword_index = KeywordIndex(session)
        self._graph = KnowledgeGraph(session)
        self._linker = DocumentLinker(session)
        self._repo = DocumentRepository(session)
        self._sync_repo = SyncRepository(session)

    async def run(self, connector: BaseConnector, incremental: bool = True, connector_key: str | None = None) -> dict:
        stats = {"fetched": 0, "indexed": 0, "skipped": 0, "errors": 0}
        connector_name = connector_key or connector.__class__.__name__.replace("Connector", "").lower()

        last_sync = None
        if incremental:
            last_sync = await self._sync_repo.get_last_sync(connector_name)
            if last_sync:
                log.info("ingestion.incremental", connector=connector_name, since=last_sync.isoformat())
            else:
                log.info("ingestion.first_run_full_sync", connector=connector_name)

        log_id = await self._sync_repo.start_sync(connector_name)
        log.info("ingestion.start", connector=connector_name, incremental=incremental, last_sync=str(last_sync))

        try:
            signature = inspect.signature(connector.fetch_documents)
            if "last_sync" in signature.parameters:
                documents = await connector.fetch_documents(last_sync=last_sync)
            else:
                documents = await connector.fetch_documents()
        except Exception as e:
            log.error("ingestion.fetch.failed", error=str(e))
            await self._sync_repo.finish_sync(log_id, 0, 0, 1, status="failed")
            return stats

        stats["fetched"] = len(documents)
        try:
            await self._sync_repo.update_progress(log_id, fetched=stats["fetched"], indexed=0, errors=0)
        except Exception:
            pass

        last_flush = time.monotonic()
        flush_every = 10
        for doc in documents:
            try:
                await self._process(doc, connector_key=connector_key or connector_name)
                stats["indexed"] += 1
            except Exception as e:
                log.error("ingestion.doc.error", doc_id=doc.id, error=str(e))
                stats["errors"] += 1

            # Lightweight progress heartbeat for UI.
            if (stats["indexed"] + stats["errors"]) % flush_every == 0 or (time.monotonic() - last_flush) > 2.0:
                last_flush = time.monotonic()
                try:
                    await self._sync_repo.update_progress(
                        log_id,
                        fetched=stats["fetched"],
                        indexed=stats["indexed"],
                        errors=stats["errors"],
                    )
                except Exception:
                    pass

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

    async def _process(self, doc: Document, *, connector_key: str) -> None:
        sections = None
        if doc.source == SourceType.CONFLUENCE:
            raw_html = doc.metadata.get("raw_html", "")
            if raw_html:
                from connectors.confluence.confluence_parser import ConfluenceParser

                sections = ConfluenceParser().parse_sections(raw_html)
                log.info("ingestion.sections", doc_id=doc.id, count=len(sections))

        doc.content = self._cleaner.clean(doc.content)
        if not doc.content:
            log.debug("ingestion.skip.empty", doc_id=doc.id)
            return

        # Persist instance lineage so multi-instance dashboards and clears can target a specific connector key.
        try:
            if not isinstance(doc.metadata, dict):
                doc.metadata = {}
            doc.metadata["connector_key"] = str(connector_key or "").strip()
        except Exception:
            pass

        extracted_entities = self._entities.extract_typed(f"{doc.title}\n{doc.content}")
        resolved_identities = self._identities.resolve(doc)
        doc.entities = [entity.name for entity in extracted_entities]

        doc.metadata = self._metadata.extract(doc)
        doc.metadata["entities"] = [
            {"name": entity.name, "type": entity.entity_type}
            for entity in extracted_entities
        ]
        doc.metadata["identities"] = [
            {
                "name": identity.canonical_name,
                "aliases": [
                    {
                        "value": alias.value,
                        "type": alias.alias_type,
                        "strength": alias.strength,
                    }
                    for alias in identity.aliases
                ],
            }
            for identity in resolved_identities
        ]

        # Keep doc.id consistent with the actual DB row id (conflict keeps old id).
        doc.id = await self._repo.upsert(doc)
        await self._graph.link_document_identities(doc.id, resolved_identities)
        await self._graph.link_document_entities(doc.id, extracted_entities)
        # Best-effort explicit cross-document links (URLs, Jira keys, SMB paths).
        try:
            await self._linker.upsert_for_document(doc.id, f"{doc.title}\n{doc.content}")
        except Exception:
            # Link extraction should not block ingestion.
            pass

        chunks = self._smart_chunk(doc, sections)
        if not chunks:
            log.warning("ingestion.skip.no_chunks", doc_id=doc.id)
            return

        await self._vector_index.index_chunks(
            chunks,
            source=doc.source.value if hasattr(doc.source, "value") else str(doc.source),
            title=doc.title,
        )
        await self._keyword_index.index_chunks(chunks)

        log.info("ingestion.doc.done", doc_id=doc.id, source=doc.source.value, chunks=len(chunks))

    def _smart_chunk(self, doc: Document, sections=None) -> list:
        if sections:
            chunks = self._chunker.chunk_by_sections(doc.id, sections, doc_title=doc.title)
            log.info("ingestion.chunk.semantic", doc_id=doc.id, chunks=len(chunks))
            return chunks

        if doc.source == SourceType.SLACK:
            chunks = self._chunker.chunk_slack(doc.id, doc.content)
            log.info("ingestion.chunk.slack", doc_id=doc.id, chunks=len(chunks))
            return chunks

        if doc.source == SourceType.JIRA:
            chunks = self._chunker.chunk_jira(doc.id, doc.content)
            log.info("ingestion.chunk.jira", doc_id=doc.id, chunks=len(chunks))
            return chunks

        if doc.source == SourceType.FILE_SERVER:
            chunks = self._chunker.chunk_file(doc.id, doc.content)
            log.info("ingestion.chunk.file", doc_id=doc.id, chunks=len(chunks))
            return chunks

        chunks = self._chunker.chunk(doc.id, doc.content)
        log.info("ingestion.chunk.word", doc_id=doc.id, chunks=len(chunks))
        return chunks
