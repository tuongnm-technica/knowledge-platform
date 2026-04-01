import pytest
from unittest.mock import AsyncMock, patch
from utils.embeddings import get_embedding, get_embeddings_batch
from utils.embedding_cache import clear_cache, get_cache_stats

@pytest.fixture(autouse=True)
def setup_teardown():
    clear_cache()
    yield
    clear_cache()

@pytest.mark.asyncio
async def test_get_embedding_cache_hit(mocker):
    text = "hello world"
    vector = [0.1, 0.2, 0.3]
    
    # Mock cache to return a vector
    mocker.patch("utils.embeddings.get_embedding_cached", new_callable=AsyncMock, return_value=vector)
    # Mock Ollama call to ensure it's NOT called
    mock_ollama = mocker.patch("utils.embeddings._call_ollama_embed", new_callable=AsyncMock)
    
    result = await get_embedding(text)
    
    assert result == vector
    mock_ollama.assert_not_called()

@pytest.mark.asyncio
async def test_get_embedding_cache_miss(mocker):
    text = "new text"
    vector = [0.4, 0.5, 0.6]
    
    # Mock cache to return None (miss)
    mocker.patch("utils.embeddings.get_embedding_cached", new_callable=AsyncMock, return_value=None)
    # Mock Ollama call to return vector
    mock_ollama = mocker.patch("utils.embeddings._call_ollama_embed", new_callable=AsyncMock, return_value=vector)
    # Mock cache set
    mock_set_cache = mocker.patch("utils.embeddings.set_embedding_cached", new_callable=AsyncMock)
    
    result = await get_embedding(text)
    
    assert result == vector
    mock_ollama.assert_called_once_with(text)
    mock_set_cache.assert_called_once_with(text, vector)

@pytest.mark.asyncio
async def test_get_embeddings_batch(mocker):
    texts = ["text1", "text2"]
    vectors = [[0.1, 0.1], [0.2, 0.2]]
    
    # Mock cache: text1 hit, text2 miss
    mock_get_cache = mocker.patch("utils.embeddings.get_embedding_cached", new_callable=AsyncMock)
    mock_get_cache.side_effect = [vectors[0], None]
    
    # Mock Ollama batch call for text2
    mock_ollama_batch = mocker.patch("utils.embeddings._call_ollama_embed_batch", new_callable=AsyncMock, return_value=[vectors[1]])
    
    # Mock cache set
    mock_set_cache = mocker.patch("utils.embeddings.set_embedding_cached", new_callable=AsyncMock)
    
    results = await get_embeddings_batch(texts)
    
    assert results == vectors
    assert mock_get_cache.call_count == 2
    mock_ollama_batch.assert_called_once_with(["text2"])
    mock_set_cache.assert_called_once_with("text2", vectors[1])
