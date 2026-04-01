import pytest
from httpx import AsyncClient
from apps.api.server import app

@pytest.mark.asyncio
async def test_health_check(mocker):
    # Mock settings to avoid side effects
    mocker.patch("apps.api.server.settings.APP_NAME", "Test App")
    mocker.patch("apps.api.server.settings.APP_VERSION", "1.0.0")
    
    # Mock lifespan components if needed, but for /health they might not be hit
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Test App"
    assert data["version"] == "1.0.0"
