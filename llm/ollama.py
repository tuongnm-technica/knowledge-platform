from __future__ import annotations

from typing import Any

import httpx
import structlog

from config.settings import settings
from .base import ILLMClient

log = structlog.get_logger()


async def _ollama_chat_raw(
    model: str,
    messages: list[dict],
    *,
    options: dict | None = None,
    timeout: int = 120,
    client: httpx.AsyncClient,
    base_url: str,
) -> str:
    """Low-level call to Ollama's /api/chat endpoint."""
    payload = {"model": model, "messages": messages, "stream": False}
    if options:
        payload["options"] = options

    full_url = f"{base_url.rstrip('/')}/api/chat"

    try:
        resp = await client.post(full_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data.get("message", {}) or {}).get("content", "")
    except httpx.HTTPStatusError as e:
        log.error("ollama.chat.status_error", url=full_url, status_code=e.response.status_code, response=e.response.text[:200])
        raise
    except Exception as e:
        log.error("ollama.chat.error", url=full_url, error=str(e))
        raise


class OllamaLLMClient(ILLMClient):
    """LLM client implementation for Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 180,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._model = model or settings.OLLAMA_LLM_MODEL
        self._base_url = base_url or settings.OLLAMA_BASE_URL
        self._managed_client = False
        if http_client:
            self._client = http_client
        else:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
            self._managed_client = True

    async def chat(self, system: str, user: str, max_tokens: int = 400, **kwargs: Any) -> str:
        """Generates a chat completion using an Ollama model."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        if "images" in kwargs and kwargs["images"]:
            user_message = next((m for m in messages if m["role"] == "user"), None)
            if user_message:
                user_message["images"] = kwargs["images"]

        model = kwargs.get("model") or self._model

        return await _ollama_chat_raw(
            model=model,
            messages=messages,
            options={"num_predict": max_tokens, "temperature": 0.1},
            client=self._client,
            base_url=self._base_url,
        )