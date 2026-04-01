import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from orchestration.agent_tasks import run_workflow_job

@pytest.fixture
def mock_db_session(mocker):
    session = AsyncMock()
    session.__aenter__.return_value = session
    mocker.patch("orchestration.agent_tasks.AsyncSessionLocal", return_value=session)
    return session

@pytest.fixture
def mock_workflow_repo(mocker):
    repo = mocker.patch("persistence.workflow_repository.WorkflowRepository").return_value
    repo.get_with_nodes = AsyncMock()
    return repo

@pytest.fixture
def mock_llm_service(mocker):
    llm = mocker.patch("services.llm_service.LLMService").return_value
    llm.chat = AsyncMock()
    return llm

@pytest.mark.asyncio
async def test_run_workflow_job_success(mock_db_session, mock_workflow_repo, mock_llm_service):
    job_id = "wf-job"
    workflow_id = "wf-123"
    initial_context = "Start data"
    
    # Mock workflow with 2 nodes
    mock_workflow_repo.get_with_nodes.return_value = {
        "name": "Test Workflow",
        "nodes": [
            {"name": "Step 1", "system_prompt": "Input: {{START}}", "step_order": 1},
            {"name": "Step 2", "system_prompt": "Prev: {{node_1_output}}", "step_order": 2}
        ]
    }
    
    # Mock LLM responses
    mock_llm_service.chat.side_effect = ["Output 1", "Output 2"]
    
    await run_workflow_job({}, job_id, "user", workflow_id, initial_context)
    
    # Verify LLM calls and context passing
    assert mock_llm_service.chat.call_count == 2
    
    # Check first call has substituted {{START}}
    args1, kwargs1 = mock_llm_service.chat.call_args_list[0]
    assert "Input: Start data" in kwargs1["user"]
    
    # Check second call has substituted {{node_1_output}}
    args2, kwargs2 = mock_llm_service.chat.call_args_list[1]
    assert "Prev: Output 1" in kwargs2["user"]
    
    # Verify we had multiple execute calls (running, thoughts, completed)
    assert mock_db_session.execute.call_count >= 3
    assert mock_db_session.commit.call_count >= 3
