import pytest
import uuid
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.llm_service import LLMService
from storage.db.db import LLMModelORM

@pytest.fixture
def mock_model_obj():
    model = MagicMock(spec=LLMModelORM)
    model.id = uuid.uuid4()
    model.llm_model_name = "test-model"
    model.config = {"temperature": 0.5}
    model.api_key = "test-key"
    model.provider = "ollama"
    model.base_url = "http://localhost:11434"
    model.is_active = True
    return model

@pytest.mark.asyncio
async def test_llm_service_resolve_model_config(mocker, mock_model_obj):
    # Mock AsyncSessionLocal to return our mock model
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_model_obj
    mock_session.execute.return_value = mock_result
    
    with patch("services.llm_service.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        service = LLMService(model_id=mock_model_obj.id)
        model_name, config, api_key, provider, base_url = await service._resolve_model_config()
        
        assert model_name == "test-model"
        assert config == {"temperature": 0.5}
        assert api_key == "test-key"
        assert provider == "ollama"
        assert base_url == "http://localhost:11434"

@pytest.mark.asyncio
async def test_llm_service_chat_success(mocker, mock_model_obj):
    # Mock resolve_model_config
    mocker.patch("services.llm_service.LLMService._resolve_model_config", 
                 return_value=("test-model", {"temp": 0.1}, "key", "ollama", "url"))
    
    # Mock get_llm_provider
    mock_provider = AsyncMock()
    mock_provider.chat.return_value = "Hello world"
    mocker.patch("services.llm_service.get_llm_provider", return_value=mock_provider)
    
    service = LLMService()
    response = await service.chat(system="You are help", user="Hi")
    
    assert response == "Hello world"
    mock_provider.chat.assert_called_once()

@pytest.mark.asyncio
async def test_llm_service_embed_success(mocker, mock_model_obj):
    # Mock resolve_model_config
    mocker.patch("services.llm_service.LLMService._resolve_model_config", 
                 return_value=("embed-model", {}, None, "ollama", "url"))
    
    # Mock get_llm_provider
    mock_provider = AsyncMock()
    mock_provider.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("services.llm_service.get_llm_provider", return_value=mock_provider)
    
    service = LLMService(task_type="embedding")
    response = await service.embed(input_text="test")
    
    assert response == [0.1, 0.2, 0.3]
    mock_provider.embed.assert_called_once()
