import re
import httpx
import structlog
from typing import Any, List, Optional, Dict
from .llm_provider import BaseLLMProvider
from config.settings import settings

log = structlog.get_logger(__name__)

class OllamaProvider(BaseLLMProvider):
    """
    Inference provider for Ollama API.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _messages_to_generate(self, messages: List[Dict[str, Any]]) -> tuple[str, Optional[str], List[str]]:
        """
        Convert chat-style messages into /api/generate payload pieces.
        """
        system = None
        prompt_parts: List[str] = []
        images: List[str] = []

        for msg in messages or []:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "").strip().lower()
            content = str(msg.get("content") or "").strip()
            if role == "system" and system is None and content:
                system = content
                continue
            if content:
                label = role.upper() if role else "MSG"
                prompt_parts.append(f"{label}:\n{content}".strip())
            
            raw_images = msg.get("images") or []
            if isinstance(raw_images, list):
                for img in raw_images:
                    s = str(img or "").strip()
                    if s:
                        images.append(s)

        prompt = "\n\n".join(prompt_parts).strip()
        return (prompt, system, images)

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        payload_chat = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options or {"temperature": 0.1},
        }

        actual_timeout = timeout or settings.LLM_TIMEOUT

        async with httpx.AsyncClient(timeout=actual_timeout) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload_chat)
                if resp.status_code == 404:
                    log.warning("ollama.chat_404_fallback", model=model)
                    return await self._fallback_generate(client, model, messages, options, actual_timeout)
                
                resp.raise_for_status()
                data = resp.json()
                msg = data.get("message", {}) if isinstance(data, dict) else {}
                out = str(msg.get("content", "") or "")
                out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL)
                return out.strip()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return await self._fallback_generate(client, model, messages, options, actual_timeout)
                raise

    async def _fallback_generate(
        self,
        client: httpx.AsyncClient,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]],
        timeout: float
    ) -> str:
        prompt, system, images = self._messages_to_generate(messages)
        payload_gen = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {"temperature": 0.1},
        }
        if system:
            payload_gen["system"] = system
        if images:
            payload_gen["images"] = images

        resp = await client.post(f"{self.base_url}/api/generate", json=payload_gen)
        resp.raise_for_status()
        data = resp.json()
        out = str((data or {}).get("response", "") or "")
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL)
        return out.strip()

    async def embed(
        self,
        model: str,
        input: str | List[str],
        timeout: Optional[float] = None,
    ) -> List[float] | List[List[float]]:
        payload = {
            "model": model,
            "input": input,
        }
        async with httpx.AsyncClient(timeout=timeout or settings.LLM_TIMEOUT * 2) as client:
            resp = await client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", []) or data.get("embedding", [])

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
