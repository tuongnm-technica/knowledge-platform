import pytest
import httpx
from unittest.mock import AsyncMock, patch
from utils.ollama_api import ollama_chat, _messages_to_generate

def test_messages_to_generate():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!", "images": ["base64img1"]},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Look at this", "images": ["base64img2"]}
    ]
    prompt, system, images = _messages_to_generate(messages)
    
    assert system == "You are a helpful assistant."
    assert "USER:\nHello!" in prompt
    assert "ASSISTANT:\nHi there!" in prompt
    assert images == ["base64img1", "base64img2"]

@pytest.mark.asyncio
async def test_ollama_chat_success(mocker):
    mock_resp = mocker.Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "Hello from Ollama"}}
    mock_resp.raise_for_status = mocker.Mock()
    
    # Mock httpx.AsyncClient.post
    mock_post = mocker.patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp)
    
    messages = [{"role": "user", "content": "Hi"}]
    response = await ollama_chat(model="llama3", messages=messages)
    
    assert response == "Hello from Ollama"
    mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_ollama_chat_fallback(mocker):
    # 1st call returns 404
    mock_resp_404 = mocker.Mock()
    mock_resp_404.status_code = 404
    mock_resp_404.request = mocker.Mock()
    
    # 2nd call (fallback) returns 200
    mock_resp_gen = mocker.Mock()
    mock_resp_gen.status_code = 200
    mock_resp_gen.json.return_value = {"response": "Fallback response"}
    mock_resp_gen.raise_for_status = mocker.Mock()
    
    mock_post = mocker.patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    mock_post.side_effect = [mock_resp_404, mock_resp_gen]
    
    messages = [{"role": "user", "content": "Hi"}]
    response = await ollama_chat(model="llama3", messages=messages)
    
    assert response == "Fallback response"
    assert mock_post.call_count == 2
