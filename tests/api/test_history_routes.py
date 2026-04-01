import pytest
from httpx import AsyncClient
from apps.api.server import app
from unittest.mock import AsyncMock

@pytest.fixture
def mock_session_repo(mocker):
    # Mock the ChatSessionRepository class used in history routes
    mock_cls = mocker.patch("apps.api.routes.history.ChatSessionRepository")
    instance = mock_cls.return_value
    instance.get_sessions = AsyncMock()
    instance.get_session_messages = AsyncMock()
    return instance

@pytest.mark.asyncio
async def test_get_history_sessions(mock_session_repo):
    # Setup mock return
    mock_session_repo.get_sessions.return_value = [
        {"id": "sess-1", "title": "Coffee basics"},
        {"id": "sess-2", "title": "Remote work policy"}
    ]
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/history/sessions?user_id=user-123")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "sess-1"

@pytest.mark.asyncio
async def test_get_session_messages(mock_session_repo):
    # Setup mock return
    mock_session_repo.get_session_messages.return_value = [
        {"id": "msg-1", "role": "user", "content": "hello"},
        {"id": "msg-2", "role": "assistant", "content": "hi there"}
    ]
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/history/sessions/sess-1/messages?user_id=user-123")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[1]["content"] == "hi there"
