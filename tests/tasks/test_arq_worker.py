import pytest
from unittest.mock import AsyncMock, MagicMock
import arq_worker

@pytest.fixture
def mock_settings(mocker):
    mocker.patch("arq_worker.settings.DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    mocker.patch("arq_worker.settings.REDIS_URL", "redis://localhost:6379/1")
    return arq_worker.settings

@pytest.mark.asyncio
async def test_worker_startup_shutdown(mock_settings, mocker):
    # Mock create_async_engine
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mocker.patch("arq_worker.create_async_engine", return_value=mock_engine)
    
    ctx = {}
    # Test startup
    await arq_worker.startup(ctx)
    assert "db_engine" in ctx
    assert "db_session_factory" in ctx
    
    # Test shutdown
    await arq_worker.shutdown(ctx)
    mock_engine.dispose.assert_called_once()

def test_worker_settings_definitions():
    # Verify IngestionWorkerSettings
    assert arq_worker.sync_connector_job in arq_worker.IngestionWorkerSettings.functions
    assert arq_worker.scan_sources_job in arq_worker.IngestionWorkerSettings.functions
    
    # Verify AIWorkerSettings
    assert arq_worker.run_agent_job_proxy in arq_worker.AIWorkerSettings.functions
    assert arq_worker.run_workflow_job_proxy in arq_worker.AIWorkerSettings.functions
    
    # Verify RedisSettings call
    from arq.connections import RedisSettings
    assert RedisSettings.from_dsn.called

@pytest.mark.asyncio
async def test_fast_background_job():
    ctx = {}
    result = await arq_worker.fast_background_job(ctx, "test-data")
    assert result is True
