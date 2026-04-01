import pytest
from httpx import AsyncClient
from apps.api.server import app
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_db_session(mocker):
    session = AsyncMock()
    # Mock AsyncSessionLocal in ask routes
    mocker.patch("apps.api.routes.ask.AsyncSessionLocal", return_value=session)
    return session

@pytest.fixture
def mock_arq(mocker):
    mock_arq_cls = mocker.patch("apps.api.routes.ask.Redis")
    instance = mock_arq_cls.return_value
    instance.enqueue_job = AsyncMock()
    return instance

@pytest.mark.asyncio
async def test_ask_async_job_creation(mock_db_session, mock_arq):
    # Mocking the database insertion of a new ChatJob
    mock_db_session.execute = AsyncMock()
    
    payload = {
        "question": "What is the policy for remote work?",
        "user_id": "user-456",
        "stream": False # Testing async background job flow
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/ask", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    
    # Verify that arq job was enqueued
    mock_arq.enqueue_job.assert_called_once_with("run_agent_job_proxy", 
                                                 job_id=pytest.any, 
                                                 user_id="user-456", 
                                                 question="What is the policy for remote work?",
                                                 session_id=None,
                                                 llm_model_id=None)
    
@pytest.mark.asyncio
async def test_ask_invalid_payload():
    payload = {
        "user_id": "user-456" # Missing 'question'
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/ask", json=payload)
    
    assert response.status_code == 422 # FastAPI validation error
