import pytest
import httpx
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from connectors.zoom.zoom_client import ZoomClient

@pytest.fixture
def zoom_client():
    return ZoomClient(
        account_id="acc123",
        client_id="cid123",
        client_secret="csec123"
    )

@pytest.mark.asyncio
async def test_zoom_get_access_token(mocker, zoom_client):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "token123", "expires_in": 3600}
    mock_resp.raise_for_status = mocker.Mock()
    
    mock_client = mocker.patch("httpx.AsyncClient", autospec=True)
    mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
    
    token = await zoom_client._get_access_token()
    
    assert token == "token123"
    assert zoom_client._access_token == "token123"
    assert zoom_client._token_expires_at > datetime.utcnow()

@pytest.mark.asyncio
async def test_zoom_test_connection_success(mocker, zoom_client):
    # Mock token first
    mocker.patch.object(zoom_client, "_get_access_token", new_callable=AsyncMock, return_value="token123")
    
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "user123"}
    mock_resp.raise_for_status = mocker.Mock()
    mock_resp.content = b'{"id": "user123"}'
    
    mock_client = mocker.patch("httpx.AsyncClient", autospec=True)
    mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)
    
    success = await zoom_client.test_connection()
    
    assert success is True

@pytest.mark.asyncio
async def test_zoom_list_recordings(mocker, zoom_client):
    mocker.patch.object(zoom_client, "_get_access_token", new_callable=AsyncMock, return_value="token123")
    
    meetings = [{"id": "meet123", "topic": "Discuss Project"}]
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"meetings": meetings}
    mock_resp.raise_for_status = mocker.Mock()
    mock_resp.content = b'{"meetings": []}' # placeholder for content check
    
    mock_client = mocker.patch("httpx.AsyncClient", autospec=True)
    mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)
    
    result = await zoom_client.list_recordings()
    
    assert result == meetings
