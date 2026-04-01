import pytest
from unittest.mock import AsyncMock, MagicMock
import retrieval.query_expansion as expansion

@pytest.fixture(autouse=True)
def clear_cache():
    expansion._cache.clear()

@pytest.mark.asyncio
async def test_expand_query_no_llm():
    query = "test query"
    results = await expansion.expand_query(query, use_llm=False)
    assert results == [query]

@pytest.mark.asyncio
async def test_expand_query_llm_success(mocker):
    # Mock ollama_chat
    mock_chat = mocker.patch("retrieval.query_expansion.ollama_chat", new_callable=AsyncMock)
    mock_chat.return_value = '{"variants": ["expanded 1", "expanded 2"]}'
    
    query = "test query"
    results = await expansion.expand_query(query, use_llm=True)
    
    assert len(results) == 3
    assert results[0] == query
    assert "expanded 1" in results
    assert "expanded 2" in results

@pytest.mark.asyncio
async def test_expand_query_cache(mocker):
    mock_chat = mocker.patch("retrieval.query_expansion.ollama_chat", new_callable=AsyncMock)
    mock_chat.return_value = '{"variants": ["expanded 1"]}'
    
    query = "test query"
    # First call
    await expansion.expand_query(query, use_llm=True)
    assert mock_chat.call_count == 1
    
    # Second call -> cache hit
    await expansion.expand_query(query, use_llm=True)
    assert mock_chat.call_count == 1

@pytest.mark.asyncio
async def test_expand_query_error_fallback(mocker):
    mock_chat = mocker.patch("retrieval.query_expansion.ollama_chat", new_callable=AsyncMock)
    mock_chat.side_effect = Exception("Ollama Error")
    
    query = "test query"
    results = await expansion.expand_query(query, use_llm=True)
    assert results == [query]
