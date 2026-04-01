import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from orchestration.agent_tasks import run_agent_job

@pytest.fixture
def mock_db_session(mocker):
    session = AsyncMock()
    session.__aenter__.return_value = session
    # Mock AsyncSessionLocal to return our mock session
    mocker.patch("orchestration.agent_tasks.AsyncSessionLocal", return_value=session)
    return session

@pytest.fixture
def mock_agent(mocker):
    agent_cls = mocker.patch("orchestration.agent_tasks.Agent")
    agent_instance = agent_cls.return_value
    agent_instance.ask = AsyncMock()
    return agent_instance

@pytest.mark.asyncio
async def test_run_agent_job_success(mock_db_session, mock_agent):
    job_id = "job-123"
    user_id = "user-abc"
    question = "Test question?"
    
    # Mock agent response
    mock_agent.ask.return_value = {
        "answer": "The answer",
        "sources": [{"title": "Source 1"}],
        "agent_plan": [{"step": 1}],
        "rewritten_query": "Rewritten question?"
    }
    
    # Run the background job
    ctx = {}
    await run_agent_job(ctx, job_id, user_id, question, session_id="sess-1")
    
    # Verify status updates
    assert mock_db_session.execute.call_count >= 2
    assert mock_db_session.commit.call_count >= 2
    
    # Verify Agent.ask call
    mock_agent.ask.assert_called_once()

@pytest.mark.asyncio
async def test_run_agent_job_failure(mock_db_session, mock_agent):
    job_id = "job-error"
    mock_agent.ask.side_effect = Exception("AI Error")
    
    await run_agent_job({}, job_id, "user", "question")
    
    # Verify last update was to status 'failed'
    last_call = mock_db_session.execute.call_args_list[-1]
    # Check that it's an 'UPDATE chat_jobs SET status = 'failed'...'
    # Since we use text(), it might be stringified differently
    assert "status = 'failed'" in str(last_call.args[0])
    assert mock_db_session.commit.called
