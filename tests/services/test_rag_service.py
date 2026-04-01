import pytest
from unittest.mock import AsyncMock, MagicMock
from services.rag_service import RAGService
from models.document import Document, SourceType

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def rag_service(mock_session, mocker):
    # Patch all dependencies in __init__
    mocker.patch("services.rag_service.HybridSearch")
    mocker.patch("services.rag_service.PermissionFilter")
    mocker.patch("services.rag_service.KnowledgeGraph")
    mocker.patch("services.rag_service.RankingScorer")
    mocker.patch("services.rag_service.DocumentRepository")
    mocker.patch("services.rag_service.AssetRepository")
    mocker.patch("services.rag_service.get_embedding_service")
    
    # Patch external functions called in methods
    mocker.patch("services.rag_service.expand_query", new_callable=AsyncMock)
    mocker.patch("services.rag_service.rerank", new_callable=AsyncMock)
    
    service = RAGService(mock_session, user_id="user-123")
    
    # Configure AsyncMock for awaited internal methods
    service._permissions.allowed_docs = AsyncMock(return_value=None) # None means all allowed
    service._search.search = AsyncMock()
    service._repo.get_by_ids = AsyncMock()
    service._assets.assets_for_chunks = AsyncMock(return_value={})
    
    # Configure scorer to return input hits with a score (to pass ContextBuilder threshold)
    service._scorer.score.side_effect = lambda hits, meta, intent: [{**h, "final_score": 0.9} for h in hits]
    
    return service

@pytest.mark.asyncio
async def test_searchv2_full_flow(rag_service, mocker):
    # Setup mocks
    rag_service._search.search.return_value = [
        {"chunk_id": "c1", "document_id": "d1", "content": "result 1", "source": "confluence"}
    ]
    rag_service._repo.get_by_ids.return_value = [
        {"id": "d1", "title": "Doc 1", "source": "confluence", "url": "http://doc1.com"}
    ]
    
    # Mock rerank to just return candidates
    from services.rag_service import rerank
    rerank.side_effect = lambda query, candidates, top_k: candidates
    
    # Run search
    results = await rag_service.searchv2("test query", limit=1, use_rerank=True)
    
    assert "hits" in results
    assert len(results["hits"]) == 1
    assert results["hits"][0]["title"] == "Doc 1"
    assert "content" in results["hits"][0]
    assert "result 1" in results["hits"][0]["content"]
    
    # Verify sequence
    rag_service._permissions.allowed_docs.assert_called_once_with("user-123")
    rag_service._search.search.assert_called()
    rerank.assert_called_once()
    rag_service._repo.get_by_ids.assert_called_once()

@pytest.mark.asyncio
async def test_searchv2_permission_denied(rag_service):
    # Mock permission filter to return empty list (no docs allowed)
    rag_service._permissions.allowed_docs.return_value = []
    
    results = await rag_service.searchv2("secret query")
    assert results == []

@pytest.mark.asyncio
async def test_searchv2_expansion_enabled(rag_service, mocker):
    mocker.patch("services.rag_service.settings.QUERY_EXPANSION_ENABLED", True)
    from services.rag_service import expand_query
    expand_query.return_value = ["expanded 1", "expanded 2"]
    
    rag_service._search.search.return_value = []
    
    await rag_service.searchv2("expand me", expand=True)
    
    # Should call search for each expanded query
    assert rag_service._search.search.call_count == 2
    expand_query.assert_called_once()
