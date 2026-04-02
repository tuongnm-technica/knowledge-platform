import pytest
import uuid
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock problematic services BEFORE importing app to avoid collection errors
with patch("storage.db.db.create_tables", new_callable=AsyncMock), \
     patch("storage.vector.vector_store.get_qdrant_client", return_value=MagicMock()), \
     patch("storage.vector.vector_store.get_qdrant", return_value=MagicMock()), \
     patch("scheduler.sync_scheduler.start_scheduler", return_value=None):
     
    from apps.api.server import app

from httpx import AsyncClient

@pytest.fixture
def mock_current_user():
    return {
        "sub": "user_123",
        "email": "test@example.com",
        "is_admin": False,
        "role": "standard"
    }

@pytest.fixture
def auth_headers(mock_current_user):
    return {"Authorization": "Bearer fake-token"}

@pytest.mark.asyncio
async def test_list_workflows_api(mocker, auth_headers, mock_current_user):
    mocker.patch("apps.api.auth.jwt_handler.decode_token", return_value=mock_current_user)
    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[{"id": "wf-1", "name": "WF 1"}])
    mocker.patch("apps.api.routes.workflows.WorkflowRepository", return_value=mock_repo)
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/workflows", headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json()["workflows"] == [{"id": "wf-1", "name": "WF 1"}]

@pytest.mark.asyncio
async def test_create_workflow_api(mocker, auth_headers, mock_current_user):
    mocker.patch("apps.api.auth.jwt_handler.decode_token", return_value=mock_current_user)
    mock_repo = MagicMock()
    mock_repo.create_workflow = AsyncMock(return_value="new-wf-id")
    mocker.patch("apps.api.routes.workflows.WorkflowRepository", return_value=mock_repo)
    
    payload = {
        "name": "New Workflow",
        "description": "Desc",
        "trigger_type": "manual",
        "nodes": [
            {"step_order": 1, "name": "Step 1", "node_type": "llm", "system_prompt": "P1"}
        ]
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/workflows", json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json()["id"] == "new-wf-id"
    assert response.json()["ok"] is True

@pytest.mark.asyncio
async def test_run_workflow_api(mocker, auth_headers, mock_current_user):
    mocker.patch("apps.api.auth.jwt_handler.decode_token", return_value=mock_current_user)
    wf_id = str(uuid.uuid4())
    run_id = "run-000"
    
    mock_repo = MagicMock()
    mock_repo.get_with_nodes = AsyncMock(return_value={"id": wf_id, "name": "Test Run", "nodes": [{"id": "n1"}]})
    mock_repo.create_run = AsyncMock(return_value=run_id)
    mocker.patch("apps.api.routes.workflows.WorkflowRepository", return_value=mock_repo)
    
    mock_redis = AsyncMock()
    mocker.patch("apps.api.routes.workflows.get_redis_pool", return_value=mock_redis)
    
    payload = {"initial_context": "Hello"}
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/workflows/{wf_id}/run", json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "job_id" in response.json()
    assert response.json()["run_id"] == run_id
    mock_redis.enqueue_job.assert_called_once()

@pytest.mark.asyncio
async def test_webhook_trigger_api(mocker):
    mock_db = AsyncMock()
    mock_wf = MagicMock()
    mock_wf.id = uuid.uuid4()
    mock_wf.name = "Webhook WF"
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_result)
    
    mocker.patch("apps.api.routes.workflows.get_db", return_value=mock_db)
    mocker.patch("apps.api.routes.workflows.get_redis_pool", return_value=AsyncMock())
    mock_repo = MagicMock()
    mock_repo.create_run = AsyncMock(return_value="run-web")
    mocker.patch("apps.api.routes.workflows.WorkflowRepository", return_value=mock_repo)
    
    token = "secret-token"
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/workflows/webhook/{token}", json={"text": "external hit"})
    
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "job_id" in response.json()
