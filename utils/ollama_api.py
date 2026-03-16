from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from config.settings import settings


log = structlog.get_logger()


def _messages_to_generate(messages: list[dict[str, Any]]) -> tuple[str, str | None, list[str]]:
    """
    Convert chat-style messages into /api/generate payload pieces.

    Returns: (prompt, system, images)
    - system: first system message (if any)
    - images: any base64 images attached to messages (Ollama expects top-level images list)
    """
    system = None
    prompt_parts: list[str] = []
    images: list[str] = []

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
        # Vision models: images may be attached on the message.
        raw_images = msg.get("images") or []
        if isinstance(raw_images, list):
            for img in raw_images:
                s = str(img or "").strip()
                if s:
                    images.append(s)

    prompt = "\n\n".join(prompt_parts).strip()
    return (prompt, system, images)


async def ollama_chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    options: dict[str, Any] | None = None,
    timeout: float | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """
    Call Ollama chat API with a safe fallback to /api/generate for older servers.

    Some deployments expose /api/tags + /api/embed but not /api/chat (404). In that case,
    we convert messages into a single prompt and use /api/generate instead.
    """
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    model = str(model or "").strip()
    if not model:
        raise ValueError("Missing model")

    payload_chat = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options or {"temperature": 0.1},
    }

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=timeout or settings.LLM_TIMEOUT)
        close_client = True

    try:
        resp = await client.post(f"{base}/api/chat", json=payload_chat, timeout=timeout or settings.LLM_TIMEOUT)
        if resp.status_code == 404:
            raise httpx.HTTPStatusError("Ollama /api/chat not found", request=resp.request, response=resp)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message", {}) if isinstance(data, dict) else {}
        out = str(msg.get("content", "") or "")
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL)
        return out.strip()

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status != 404:
            raise

        # Fallback: /api/generate
        prompt, system, images = _messages_to_generate(messages)
        payload_gen: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {"temperature": 0.1},
        }
        if system:
            payload_gen["system"] = system
        if images:
            payload_gen["images"] = images

        log.warning("ollama.chat_fallback_generate", model=model)
        resp2 = await client.post(f"{base}/api/generate", json=payload_gen, timeout=timeout or settings.LLM_TIMEOUT)
        resp2.raise_for_status()
        data2 = resp2.json()
        out = str((data2 or {}).get("response", "") or "")
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL)
        return out.strip()

    finally:
        if close_client:
            await client.aclose()

