import pytest
from unittest.mock import AsyncMock, MagicMock
from orchestration.react_loop import ReActLoop, PlanStep

@pytest.fixture
def mock_tools(mocker):
    mock_tool = MagicMock()
    mock_tool.run = AsyncMock()
    # Mock ToolResult
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.data = [{"chunk_id": "c1", "score": 0.5, "content": "text", "url": "http://doc1.com"}]
    mock_result.graph_data = set()
    mock_result.to_observation.return_value = "Result data"
    mock_tool.run.return_value = mock_result
    
    return {"search_all": mock_tool}

@pytest.fixture
def react_loop(mock_tools, mocker):
    mocker.patch("orchestration.react_loop.LLMService")
    mock_cache_cls = mocker.patch("orchestration.react_loop.SemanticCache")
    mock_cache = mock_cache_cls.return_value
    mock_cache.lookup = AsyncMock(return_value=None)
    mock_cache.store = AsyncMock()
    
    mocker.patch("orchestration.react_loop.compress_context", return_value="compressed context")
    
    loop = ReActLoop(mock_tools)
    
    # Mock all internal LLM-calling methods to be deterministic
    loop._classify_query = AsyncMock(return_value={"intent": "general", "need_graph": False})
    loop._make_plan = AsyncMock(return_value=[PlanStep(step=1, tool="search_all", query="test", reason="test")])
    loop._grade_and_rerank = AsyncMock(side_effect=lambda q, s: s)
    loop._should_retry = MagicMock(return_value=False)
    loop._rewrite_query = AsyncMock(return_value=None)
    loop._summarize = AsyncMock(return_value="Default answer")
    
    return loop

@pytest.mark.asyncio
async def test_react_loop_fast_path(react_loop, mocker):
    # Short question triggers fast path
    question = "Who is CEO?"
    react_loop._summarize.return_value = "The CEO is John Doe."
    
    result = await react_loop.run(question)
    
    assert result.answer == "The CEO is John Doe."
    assert len(result.plan) == 1
    assert result.plan[0].tool == "search_all"
    assert "search_all" in result.used_tools

@pytest.mark.asyncio
async def test_react_loop_cache_hit(react_loop, mocker):
    mocker.patch("orchestration.react_loop.settings.SEMANTIC_CACHE_ENABLED", True)
    # The cache instance is already mocked in the fixture
    react_loop._cache.lookup.return_value = "Cached answer"
    
    result = await react_loop.run("reused question")
    
    assert result.answer == "Cached answer"
    assert "semantic_cache" in result.used_tools
    # Verify no other logic (like classify) ran
    assert react_loop._classify_query.call_count == 0

@pytest.mark.asyncio
async def test_react_loop_no_answer_gate(react_loop, mocker):
    react_loop._classify_query = AsyncMock(return_value={"intent": "fact", "need_graph": False})
    
    # Mock tool to return NO data
    mock_tool = react_loop._tools["search_all"]
    mock_tool.run.return_value.data = []
    
    result = await react_loop.run("non-existent topic")
    
    assert "Không tìm thấy" in result.answer or "No relevant information" in result.answer
    assert result.sources == []

@pytest.mark.asyncio
async def test_react_loop_self_correct(react_loop, mocker):
    react_loop._classify_query = AsyncMock(return_value={"intent": "fact", "need_graph": False})
    
    # Low score results (triggering self-correct)
    mock_tool = react_loop._tools["search_all"]
    mock_tool.run.return_value.data = [{"chunk_id": "c1", "score": 0.1, "content": "weak match"}]
    
    # Mock self-correct logic
    react_loop._should_retry = MagicMock(return_value=True)
    react_loop._rewrite_query = AsyncMock(return_value="better query")
    react_loop._grade_and_rerank = AsyncMock(side_effect=lambda q, s: s) # Passthrough
    react_loop._summarize = AsyncMock(return_value="Final answer after retry")
    
    await react_loop.run("vague question")
    
    # Should have executed tool twice (original + retry)
    assert mock_tool.run.call_count == 2
    react_loop._rewrite_query.assert_called_once()
