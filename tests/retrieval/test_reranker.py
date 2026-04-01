import pytest
import time
from unittest.mock import AsyncMock, MagicMock
import retrieval.reranker as reranker

@pytest.fixture
def mock_llm_service(mocker):
    # Patch LLMService in retrieval.reranker
    mock = mocker.patch("retrieval.reranker.LLMService")
    return mock.return_value

@pytest.fixture(autouse=True)
def clear_cache():
    # Clear internal cache before each test
    reranker._rerank_cache.clear()

@pytest.mark.asyncio
async def test_rerank_skip_logic(mocker):
    # Mock settings
    mocker.patch("retrieval.reranker.settings.RERANKING_ENABLED", False)
    
    candidates = [{"chunk_id": "c1"}]
    results = await reranker.rerank("query", candidates, top_k=5)
    assert results == candidates

@pytest.mark.asyncio
async def test_rerank_high_confidence_skip(mocker):
    mocker.patch("retrieval.reranker.settings.RERANKING_ENABLED", True)
    
    # Candidate with very high RRF score (> 0.9)
    candidates = [{"chunk_id": "c1", "rrf_score": 0.95}]
    results = await reranker.rerank("query", candidates, top_k=5)
    assert results == candidates

@pytest.mark.asyncio
async def test_rerank_llm_backend(mock_llm_service, mocker):
    mocker.patch("retrieval.reranker.settings.RERANKING_ENABLED", True)
    mocker.patch("retrieval.reranker._backend_name", return_value="llm")
    
    candidates = [
        {"chunk_id": "c1", "content": "text 1", "rrf_score": 0.5},
        {"chunk_id": "c2", "content": "text 2", "rrf_score": 0.4}
    ]
    
    # Mock LLM response (score JSON)
    mock_llm_service.chat = AsyncMock(return_value='{"scores": [{"id": "c2", "score": 3}, {"id": "c1", "score": 1}]}')
    
    # Use top_k=1 to trigger reranking (since len(candidates)=2)
    results = await reranker.rerank("query", candidates, top_k=1)
    
    # c2 should now be first because it has higher LLM score
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c2"
    assert results[0]["llm_relevance"] == 3
    assert "rerank_score" in results[0]

@pytest.mark.asyncio
async def test_rerank_cache(mock_llm_service, mocker):
    mocker.patch("retrieval.reranker.settings.RERANKING_ENABLED", True)
    mocker.patch("retrieval.reranker._backend_name", return_value="llm")
    
    candidates = [
        {"chunk_id": "c1", "content": "text 1", "rrf_score": 0.5},
        {"chunk_id": "c2", "content": "text 2", "rrf_score": 0.4}
    ]
    mock_llm_service.chat = AsyncMock(return_value='{"scores": [{"id": "c1", "score": 2}]}')
    
    # First call
    await reranker.rerank("query", candidates, top_k=1)
    assert mock_llm_service.chat.call_count == 1
    
    # Second call (same query/candidates) -> cache hit
    await reranker.rerank("query", candidates, top_k=1)
    assert mock_llm_service.chat.call_count == 1

@pytest.mark.asyncio
async def test_rerank_error_fallback(mock_llm_service, mocker):
    mocker.patch("retrieval.reranker.settings.RERANKING_ENABLED", True)
    
    candidates = [
        {"chunk_id": "c1", "rrf_score": 0.5},
        {"chunk_id": "c2", "rrf_score": 0.4}
    ]
    mock_llm_service.chat = AsyncMock(side_effect=Exception("LLM Down"))
    
    results = await reranker.rerank("query", candidates, top_k=1)
    # Should fallback to original top_k results
    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"
