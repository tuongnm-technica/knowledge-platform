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
    repo.update_run_status = AsyncMock()
    return repo

@pytest.fixture
def mock_llm_service(mocker):
    llm = mocker.patch("services.llm_service.LLMService").return_value
    llm.chat = AsyncMock()
    return llm

@pytest.mark.asyncio
async def test_run_workflow_rag_node(mock_db_session, mock_workflow_repo, mock_llm_service, mocker):
    job_id = "wf-job"
    workflow_id = "wf-123"
    initial_context = "Find info about A"
    
    # Mock workflow with a RAG node
    mock_workflow_repo.get_with_nodes.return_value = {
        "name": "RAG Workflow",
        "nodes": [
            {
                "name": "RAG Search", 
                "node_type": "rag", 
                "system_prompt": "Answer based on context: {{START}}", 
                "step_order": 1
            }
        ]
    }
    
    # Mock HybridSearch
    mock_searcher = AsyncMock()
    mock_searcher.search = AsyncMock(return_value=[{"title": "Doc A", "content": "Content about A"}])
    mocker.patch("retrieval.hybrid.hybrid_search.HybridSearch", return_value=mock_searcher)
    
    mock_llm_service.chat.return_value = "Result based on Doc A"
    
    await run_workflow_job({}, job_id, "user", workflow_id, initial_context)
    
    # Verify HybridSearch was called
    mock_searcher.search.assert_awaited_once()
    

@pytest.mark.asyncio
async def test_run_workflow_doc_writer_node(mock_db_session, mock_workflow_repo, mock_llm_service):
    job_id = "wf-job"
    workflow_id = "wf-123"
    
    mock_workflow_repo.get_with_nodes.return_value = {
        "name": "Doc Workflow",
        "nodes": [
            {
                "name": "Writer", 
                "node_type": "doc_writer", 
                "system_prompt": "Write a doc about {{START}}", 
                "step_order": 1
            }
        ]
    }
    mock_llm_service.chat.return_value = "# My Doc"
    
    await run_workflow_job({}, job_id, "user", workflow_id, "Context")
    
    # Verify doc_writer specific system prompt was used
    args, kwargs = mock_llm_service.chat.call_args
    assert "Technical Writer" in kwargs["system"]
    assert "ONLY the raw Markdown" in kwargs["system"]

@pytest.mark.asyncio
async def test_run_workflow_failure_handling(mock_db_session, mock_workflow_repo, mock_llm_service):
    job_id = "wf-job"
    workflow_id = "wf-123"
    run_id = "run-1"
    
    mock_workflow_repo.get_with_nodes.return_value = {
        "name": "Failing Workflow",
        "nodes": [{"name": "Step 1", "node_type": "llm", "system_prompt": "P1", "step_order": 1}]
    }
    
    # Simulate LLM error
    mock_llm_service.chat.side_effect = Exception("LLM Down")
    
    await run_workflow_job({}, job_id, "user", workflow_id, "Context", run_id=run_id)
    
    # Verify job status updated to failed
    # We check the execute call or update_run_status
    mock_workflow_repo.update_run_status.assert_called_with(run_id, status="failed", error="LLM Down")
    
    # Check chat_jobs table update
    # In agent_tasks.py, it uses text("UPDATE chat_jobs SET status = 'failed' ...")
    # We can check call args of mock_db_session.execute
    found_failed_update = False
    for call in mock_db_session.execute.call_args_list:
        if "SET status = 'failed'" in str(call[0][0]):
            found_failed_update = True
            break
    assert found_failed_update is True
