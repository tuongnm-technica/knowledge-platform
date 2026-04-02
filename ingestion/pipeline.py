import inspect
import time
import asyncio

import structlog

from config.settings import settings
from connectors.base.base_connector import BaseConnector
from graph.entity_extractor import EntityExtractor
from graph.relation_extractor import SemanticRelationExtractor
from graph.identity_resolver import IdentityResolver
from graph.document_linker import DocumentLinker
from graph.knowledge_graph import KnowledgeGraph
from indexing.keyword_index import KeywordIndex
from indexing.vector_index import VectorIndex
from ingestion.chunker import chunk_document
from ingestion.cleaner import TextCleaner
from ingestion.metadata_extractor import MetadataExtractor
from models.document import Document, SourceType
from persistence.document_repository import DocumentRepository
from persistence.asset_repository import AssetRepository
from persistence.sync_repository import SyncRepository
from services.summarization_service import SummarizationService


log = structlog.get_logger()


class IngestionPipeline:
    """
    Luồng xử lý nạp dữ liệu (Ingestion Pipeline).
    Phụ trách việc:
    1. Lấy dữ liệu từ các Connector (Jira, Confluence, Slack...).
    2. Làm sạch (Clean) và trích xuất Metadata.
    3. Trích xuất Thực thể (Entities) và Danh tính (Identities).
    4. Chia nhỏ văn bản (Chunking) và Vector hóa.
    5. Đánh chỉ mục (Index) vào Vector DB và Keyword Index.
    6. Cập nhật Đồ thị Tri thức (Knowledge Graph).
    """
    def __init__(self, session):
        self._session = session
        self._cleaner = TextCleaner()
        self._metadata = MetadataExtractor()
        self._entities = EntityExtractor()
        self._relation_extractor = SemanticRelationExtractor()
        self._identities = IdentityResolver()
        self._vector_index = VectorIndex(session)
        self._keyword_index = KeywordIndex(session)
        self._graph = KnowledgeGraph(session)
        self._linker = DocumentLinker(session)
        self._repo = DocumentRepository(session)
        self._sync_repo = SyncRepository(session)
        self._summarizer = SummarizationService()

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

        log_id = None
        try:
            log_id = await self._sync_repo.start_sync(connector_name)
            log.info("ingestion.start", connector=connector_name, incremental=incremental, log_id=log_id, last_sync=str(last_sync))
        except Exception as e:
            log.error("ingestion.start_sync_log.failed", connector=connector_name, error=str(e))
            # Even if logging fails, we might still want to try fetching if it's not a DB connection fatal error
            # but usually start_sync failure means DB is down.
            pass

        try:
            log.info("ingestion.fetch.start", connector=connector_name)
            signature = inspect.signature(connector.fetch_documents)
            if "last_sync" in signature.parameters:
                documents = await connector.fetch_documents(last_sync=last_sync)
            else:
                documents = await connector.fetch_documents()
            log.info("ingestion.fetch.done", connector=connector_name, count=len(documents))
        except Exception as e:
            log.error("ingestion.fetch.failed", error=str(e))
            if log_id:
                await self._sync_repo.finish_sync(log_id, 0, 0, 1, status="failed")
            return stats

        stats["fetched"] = len(documents)
        try:
            await self._sync_repo.update_progress(log_id, fetched=stats["fetched"], indexed=0, errors=0)
        except Exception:
            pass

        # Process documents in smaller batches to avoid job timeout (ARQ default ~300s)
        # Batch size configurable via INGESTION_BATCH_SIZE setting
        batch_size = settings.INGESTION_BATCH_SIZE
        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch_docs = documents[batch_start:batch_end]
            
            last_flush = time.monotonic()
            flush_every = 3
            
            for doc in batch_docs:
                try:
                    log.debug("ingestion.doc.process", doc_id=doc.id, title=doc.title[:50])
                    await self._process(doc, connector_key=connector_key or connector_name)
                    stats["indexed"] += 1
                except Exception as e:
                    log.error("ingestion.doc.error", doc_id=doc.id, error=str(e))
                    stats["errors"] += 1
                    await self._session.rollback()

                # Lightweight progress heartbeat for UI.
                if (stats["indexed"] + stats["errors"]) % flush_every == 0 or (time.monotonic() - last_flush) > 2.0:
                    last_flush = time.monotonic()
                    try:
                        still_running = await self._sync_repo.update_progress(
                            log_id,
                            fetched=stats["fetched"],
                            indexed=stats["indexed"],
                            errors=stats["errors"],
                        )
                        if not still_running:
                            log.warning("ingestion.cancelled_by_user", log_id=log_id)
                            # Update status explicitly to cancelled so finish_sync doesn't override it to 'partial'
                            await self._sync_repo.finish_sync(
                                log_id,
                                fetched=stats["fetched"],
                                indexed=stats["indexed"],
                                errors=stats["errors"],
                                status="cancelled",
                            )
                            return stats
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
        
        # AI Summarization: Zoom/Meet (always) or Confluence (if content length >= 500 words)
        words = doc.content.split()
        if doc.source in (SourceType.ZOOM, SourceType.GOOGLE_MEET) or (doc.source == SourceType.CONFLUENCE and len(words) >= 500):
            try:
                summary = await self._summarizer.summarize(doc.content, doc.source, doc.title)
                if summary:
                    doc.summary = summary
                    # Prepend summary to content for better search priority
                    doc.content = f"[SUMMARY]\n{summary}\n[/SUMMARY]\n\n{doc.content}"
            except Exception as e:
                log.error("ingestion.summary.failed", doc_id=doc.id, error=str(e))

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

        # First persist to get the canonical document id (upsert may keep an existing row id).
        doc.id = await self._repo.upsert(doc)

        # Enrich with image assets (download/stage + optional caption/OCR) before embeddings.
        # This makes text queries match screenshots/diagrams via injected captions.
        replacements: dict[str, str] = {}
        try:
            from ingestion.assets_ingestor import AssetIngestor

            enriched = await AssetIngestor(self._session).enrich_document(doc)
            if enriched.get("ingested", 0) > 0:
                doc.content = str(enriched.get("content") or doc.content)
                replacements = enriched.get("replacements") or {}
                if isinstance(doc.metadata, dict):
                    doc.metadata["asset_count"] = int(enriched.get("ingested") or 0)
                    doc.metadata["assets_ingested"] = True
        except asyncio.TimeoutError as exc:
            log.error("ingestion.assets.enrich_timeout", doc_id=doc.id, error=str(exc))
        except asyncio.CancelledError:
            log.warning("ingestion.assets.cancelled", doc_id=doc.id)
            raise  # Bắt buộc phải raise lại để luồng Worker ARQ có thể huỷ Job đúng cách
        except Exception as exc:
            log.warning("ingestion.assets.enrich_failed", doc_id=doc.id, error=str(exc))

        # If we use Confluence semantic sections, also inject the same replacements there so chunking keeps the link.
        if sections and replacements:
            try:
                for section in sections:
                    text_value = str(section.get("content") or "")
                    for raw, repl in replacements.items():
                        text_value = text_value.replace(raw, repl)
                    section["content"] = text_value
            except Exception:
                pass

        extracted_entities = self._entities.extract_typed(f"{doc.title}\n{doc.content}")
        resolved_identities = self._identities.resolve(doc)
        doc.entities = [entity.name for entity in extracted_entities]

        doc.metadata = self._metadata.extract(doc)
        doc.metadata["entities"] = [{"name": entity.name, "type": entity.entity_type} for entity in extracted_entities]
        doc.metadata["identities"] = [
            {
                "name": identity.canonical_name,
                "aliases": [
                    {"value": alias.value, "type": alias.alias_type, "strength": alias.strength}
                    for alias in identity.aliases
                ],
            }
            for identity in resolved_identities
        ]

        # Update document row with enriched content + extracted metadata.
        doc.id = await self._repo.upsert(doc)

        await self._graph.link_document_identities(doc.id, resolved_identities)
        await self._graph.link_document_entities(doc.id, extracted_entities)
        
        # Mới: Sử dụng LLM để trích xuất Semantic Relations và nhét vào DB
        # Skip cho Jira/Slack: nội dung ngắn/cấu trúc, không cần LLM relations
        # (giảm số LLM call từ N_issues → 0 cho Jira, tăng tốc ingest ~5-10x)
        _SKIP_RELATIONS_FOR = {SourceType.JIRA, SourceType.SLACK}
        if doc.source not in _SKIP_RELATIONS_FOR:
            try:
                semantic_relations = await self._relation_extractor.extract(f"{doc.title}\n{doc.content}")
                if semantic_relations:
                    source_val = doc.source.value if hasattr(doc.source, "value") else str(doc.source)
                    await self._graph.link_document_semantic_relations(doc.id, semantic_relations, source=source_val)
            except Exception as e:
                log.warning("ingestion.semantic_relations.failed", doc_id=doc.id, error=str(e))
        
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

        # Link chunk <-> asset ids for downstream vision context selection.
        try:
            from ingestion.assets_ingestor import AssetIngestor

            repo = AssetRepository(self._session)
            max_assets = max(1, int(settings.VISION_MAX_IMAGES_PER_CHUNK or 3))
            for chunk in chunks:
                asset_ids = AssetIngestor.extract_asset_ids(chunk.content)
                if asset_ids:
                    await repo.link_chunk_assets(chunk_id=chunk.id, asset_ids=list(dict.fromkeys(asset_ids))[:max_assets])
        except Exception:
            pass

        log.info("ingestion.doc.done", doc_id=doc.id, source=doc.source.value, chunks=len(chunks))

    def _smart_chunk(self, doc: Document, sections=None) -> list:
        kwargs = {"content": doc.content}
        if sections:
            kwargs["sections"] = sections
            kwargs["doc_title"] = doc.title
            
        chunks = chunk_document(doc.source, doc.id, **kwargs)
        log.info("ingestion.chunk.smart", doc_id=doc.id, chunks=len(chunks), source=str(doc.source))
        return chunks
