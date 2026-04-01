import pytest
from unittest.mock import AsyncMock, MagicMock
from retrieval.hybrid.hybrid_search import HybridSearch

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def hybrid_search(mock_session, mocker):
    # Patch the sub-searchers in the constructor
    mocker.patch("retrieval.hybrid.hybrid_search.VectorSearch")
    mocker.patch("retrieval.hybrid.hybrid_search.KeywordSearch")
    mocker.patch("retrieval.hybrid.hybrid_search.get_embedding", new_callable=AsyncMock)
    
    return HybridSearch(mock_session)

@pytest.mark.asyncio
async def test_hybrid_search_rrf_merge(hybrid_search, mocker):
    # Setup mocks
    hybrid_search._vector.search = AsyncMock()
    hybrid_search._keyword.search = AsyncMock()
    
    # Mock vector results
    hybrid_search._vector.search.return_value = [
        {"chunk_id": "c1", "score": 0.9, "content": "vector result 1"},
        {"chunk_id": "c2", "score": 0.8, "content": "vector result 2"}
    ]
    
    # Mock keyword results
    hybrid_search._keyword.search.return_value = [
        {"chunk_id": "c2", "score": 0.7, "content": "keyword result 2"},
        {"chunk_id": "c3", "score": 0.6, "content": "keyword result 3"}
    ]
    
    results = await hybrid_search.search("test query", top_k=5)
    
    # Verify RRF merge logic
    assert len(results) == 3
    # c2 should have highest score because it's in both
    assert results[0]["chunk_id"] == "c2"
    assert "vector_score" in results[0]
    assert "keyword_score" in results[0]
    assert "rrf_score" in results[0]

@pytest.mark.asyncio
async def test_hybrid_search_weight_adjustment(hybrid_search, mocker):
    hybrid_search._vector.search = AsyncMock(return_value=[])
    hybrid_search._keyword.search = AsyncMock(return_value=[])
    
    # Test with acronym (should trigger higher keyword weight)
    # We can't easily assert the internal weight without spying on _rrf_merge
    spy = mocker.spy(hybrid_search, "_rrf_merge")
    
    await hybrid_search.search("What is RAG?", top_k=5)
    
    # In hybrid_search.py:
    # if is_date or is_acronym:
    #     keyword_weight = 0.75
    #     vector_weight = 0.25
    
    args, _ = spy.call_args
    # args: (vector_results, keyword_results, vector_weight, keyword_weight)
    assert args[3] == 0.75 # keyword_weight
    assert args[2] == 0.25 # vector_weight

@pytest.mark.asyncio
async def test_hybrid_search_error_handling(hybrid_search):
    # Force error in get_embedding
    from retrieval.hybrid.hybrid_search import get_embedding
    get_embedding.side_effect = Exception("Embed error")
    
    results = await hybrid_search.search("error query")
    assert results == []
