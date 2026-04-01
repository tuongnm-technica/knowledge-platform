import pytest
from httpx import AsyncClient
from apps.api.server import app
from unittest.mock import AsyncMock

@pytest.fixture
def mock_rag_service(mocker):
    # Mock the RAGService class in the search routes module
    mock_cls = mocker.patch("apps.api.routes.search.RAGService")
    instance = mock_cls.return_value
    instance.searchv2 = AsyncMock()
    return instance

@pytest.mark.asyncio
async def test_search_results(mock_rag_service):
    # Setup mock data
    mock_rag_service.searchv2.return_value = {
        "results": [
            {"document_id": "doc1", "content": "text 1", "score": 0.9},
            {"document_id": "doc2", "content": "text 2", "score": 0.8}
        ],
        "metadata": {"count": 2}
    }
    
    payload = {
        "raw": "How to brew coffee?",
        "user_id": "user-123",
        "limit": 5
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/search", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["document_id"] == "doc1"
    
    # Verify RAGService was called correctly
    mock_rag_service.searchv2.assert_called_once()
    called_query = mock_rag_service.searchv2.call_args[0][0]
    assert called_query.raw == "How to brew coffee?"
