import pytest
from unittest.mock import AsyncMock, MagicMock
from orchestration.agent import Agent
from orchestration.react_loop import ReActResult, ReActStep

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def agent(mock_session, mocker):
    mocker.patch("orchestration.agent.LLMService")
    mocker.patch("orchestration.agent.build_tool_registry")
    mocker.patch("orchestration.agent.ReActLoop")
    mocker.patch("orchestration.agent.QueryLogRepository")
    mocker.patch("orchestration.agent.AssetRepository")
    
    a = Agent(mock_session, user_id="user-1")
    # Setup some defaults
    a._session_id = "sess-123" # Mocking session presence
    return a

@pytest.mark.asyncio
async def test_agent_ask_success(agent, mocker):
    # Get the patched ReActLoop class
    import orchestration.agent as agent_module
    mock_loop_cls = agent_module.ReActLoop
    mock_loop = mock_loop_cls.return_value
    
    mock_loop.run = AsyncMock()
    mock_loop.run.return_value = ReActResult(
        answer="Hello world",
        plan=[],
        steps=[ReActStep(iteration=1, thought="Thinking", action="finish", observation="done", is_final=True)],
        sources=[{"document_id": "d1", "title": "Doc 1", "score": 0.9}],
        used_tools=["tool1"]
    )
    mock_loop.close = AsyncMock()
    
    # Run agent.ask
    response = await agent.ask("Who are you?")
    
    assert response["answer"] == "Hello world"
    assert len(response["sources"]) == 1
    
    # Verify DB logging called
    agent_module.QueryLogRepository.return_value.log_query.assert_called_once()

@pytest.mark.asyncio
async def test_agent_search_delegation(agent, mocker):
    # Mock httpx response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"document_id": "d1", "content": "text", "score": 1.0}]}
    mock_resp.raise_for_status = MagicMock()
    
    # Mock the post method
    mock_post = AsyncMock(return_value=mock_resp)
    
    # Mock the AsyncClient class as a context manager
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        post = mock_post
        
    mocker.patch("orchestration.agent.httpx.AsyncClient", return_value=MockClient())
    
    from models.query import SearchQuery
    sq = SearchQuery(raw="test", user_id="user-1")
    
    results = await agent.search(sq)
    assert len(results) == 1
    assert results[0].document_id == "d1"
    assert mock_post.called
