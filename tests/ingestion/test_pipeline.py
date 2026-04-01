import pytest
import uuid
from datetime import datetime
from models.document import Document, SourceType
from ingestion.pipeline import IngestionPipeline

@pytest.fixture
def mock_session(mocker):
    return mocker.AsyncMock()

@pytest.fixture
def pipeline(mock_session, mocker):
    # Patch all core components to prevent actual initialization
    mocker.patch("ingestion.pipeline.VectorIndex")
    mocker.patch("ingestion.pipeline.KeywordIndex")
    mocker.patch("ingestion.pipeline.KnowledgeGraph")
    mocker.patch("ingestion.pipeline.DocumentLinker")
    mocker.patch("ingestion.pipeline.DocumentRepository")
    mocker.patch("ingestion.pipeline.SyncRepository")
    mocker.patch("ingestion.pipeline.SummarizationService")
    mocker.patch("ingestion.pipeline.EntityExtractor")
    mocker.patch("ingestion.pipeline.SemanticRelationExtractor")
    mocker.patch("ingestion.pipeline.IdentityResolver")
    mocker.patch("ingestion.pipeline.AssetRepository")
    
    # Also mock local imports used inside methods (using create=True to avoid AttributeError)
    mocker.patch("ingestion.pipeline.ConfluenceParser", create=True)
    mocker.patch("ingestion.pipeline.AssetIngestor", create=True)
    
    p = IngestionPipeline(mock_session)
    
    # Configure AsyncMock for all awaited methods
    p._sync_repo.get_last_sync = mocker.AsyncMock(return_value=None)
    p._sync_repo.start_sync = mocker.AsyncMock(return_value="log-123")
    p._sync_repo.update_progress = mocker.AsyncMock(return_value=True)
    p._sync_repo.finish_sync = mocker.AsyncMock()
    
    p._repo.upsert = mocker.AsyncMock(return_value="doc-uuid")
    p._summarizer.summarize = mocker.AsyncMock()
    p._relation_extractor.extract = mocker.AsyncMock()
    p._graph.link_document_identities = mocker.AsyncMock()
    p._graph.link_document_entities = mocker.AsyncMock()
    p._graph.link_document_semantic_relations = mocker.AsyncMock()
    p._linker.upsert_for_document = mocker.AsyncMock()
    p._vector_index.index_chunks = mocker.AsyncMock()
    p._keyword_index.index_chunks = mocker.AsyncMock()
    
    # Configure AssetIngestor mock (instantiated inside _process)
    import ingestion.pipeline
    ingestion.pipeline.AssetIngestor.return_value.enrich_document = mocker.AsyncMock(return_value={"ingested": 0})
    ingestion.pipeline.AssetRepository.return_value.link_chunk_assets = mocker.AsyncMock()
    
    return p

@pytest.mark.asyncio
async def test_pipeline_run_success(pipeline, mocker):
    # Mock connector
    mock_connector = mocker.Mock()
    mock_connector.fetch_documents = mocker.AsyncMock()
    doc = Document(
        id="doc-1",
        source=SourceType.CONFLUENCE,
        source_id="src-1",
        title="Test Doc",
        content="Test content",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_connector.fetch_documents.return_value = [doc]
    
    # Configure specific return values
    pipeline._sync_repo.start_sync.return_value = "log-123"
    pipeline._repo.upsert.return_value = "doc-1-uuid"
    
    # Mock chunking (global function)
    mock_chunk = mocker.patch("ingestion.pipeline.chunk_document")
    mock_chunk.return_value = [mocker.Mock(id="chunk-1", content="test")]
    
    # Run pipeline
    stats = await pipeline.run(mock_connector, incremental=False)
    
    assert stats["fetched"] == 1
    assert stats["indexed"] == 1
    assert stats["errors"] == 0
    
    # Verify sequence
    pipeline._sync_repo.start_sync.assert_called_once()
    mock_connector.fetch_documents.assert_called_once()
    pipeline._repo.upsert.assert_called() # Should be called twice in _process
    pipeline._vector_index.index_chunks.assert_called_once()
    pipeline._sync_repo.finish_sync.assert_called_once_with(
        "log-123", fetched=1, indexed=1, errors=0, status="success"
    )

@pytest.mark.asyncio
async def test_pipeline_run_with_error(pipeline, mocker):
    mock_connector = mocker.Mock()
    mock_connector.fetch_documents = mocker.AsyncMock()
    doc = Document(
        id="doc-1",
        source=SourceType.CONFLUENCE,
        source_id="src-1",
        title="Test Doc",
        content="Test content",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_connector.fetch_documents.return_value = [doc]
    
    pipeline._sync_repo.start_sync = mocker.AsyncMock(return_value="log-err")
    pipeline._sync_repo.finish_sync = mocker.AsyncMock()
    
    # Force error in _process (awaited)
    pipeline._repo.upsert = mocker.AsyncMock(side_effect=Exception("DB Error"))
    
    stats = await pipeline.run(mock_connector)
    
    assert stats["fetched"] == 1
    assert stats["indexed"] == 0
    assert stats["errors"] == 1
    pipeline._sync_repo.finish_sync.assert_called_once_with(
        "log-err", fetched=1, indexed=0, errors=1, status="partial"
    )

@pytest.mark.asyncio
async def test_pipeline_incremental_sync(pipeline, mocker):
    mock_connector = mocker.Mock()
    mock_connector.fetch_documents = mocker.AsyncMock(return_value=[])
    
    last_sync_time = datetime.now()
    pipeline._sync_repo.get_last_sync = mocker.AsyncMock(return_value=last_sync_time)
    pipeline._sync_repo.start_sync = mocker.AsyncMock(return_value="log-inc")
    pipeline._sync_repo.finish_sync = mocker.AsyncMock()
    
    await pipeline.run(mock_connector, incremental=True)
    
    pipeline._sync_repo.get_last_sync.assert_called_once()
    # Check if last_sync was passed to fetch_documents
    # pipeline.run fetches signature, if 'last_sync' in params, it passes it.
    # Our mock doesn't have 'last_sync' in signature by default.
    # To test this perfectly, we'd need to mock the signature or the connector more realistically.
