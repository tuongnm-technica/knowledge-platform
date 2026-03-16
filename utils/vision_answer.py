from __future__ import annotations

import base64

import httpx
import structlog

from config.settings import settings


log = structlog.get_logger()


VISION_QA_SYSTEM = """\
You are an enterprise assistant with vision.

Use BOTH:
- the provided text context (RAG snippets)
- the provided images (screenshots/diagrams/charts/whiteboards)

Rules:
- If the context is insufficient, say what is missing.
- When referencing an image, describe what you saw concretely (labels, errors, axes, components).
- Keep the answer structured and actionable.
"""


async def answer_with_images(*, question: str, context: str, images: list[bytes]) -> str:
    if not settings.VISION_ENABLED:
        return ""
    model = str(settings.OLLAMA_VISION_MODEL or "").strip()
    if not model:
        return ""
    if not images:
        return ""

    imgs_b64 = [base64.b64encode(b).decode("ascii") for b in images if b]
    if not imgs_b64:
        return ""

    user_prompt = "\n\n".join(
        [
            f"QUESTION:\n{question}".strip(),
            "CONTEXT:",
            (context or "").strip()[:12000],
            "Answer the question using the context and the images.",
        ]
    ).strip()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": VISION_QA_SYSTEM},
            {"role": "user", "content": user_prompt, "images": imgs_b64},
        ],
        "stream": False,
        "options": {"num_predict": 700, "temperature": 0.1},
    }

    try:
        async with httpx.AsyncClient(timeout=240) as client:
            resp = await client.post(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat", json=payload)
            resp.raise_for_status()
            return str(resp.json().get("message", {}).get("content", "") or "").strip()
    except Exception as exc:
        log.warning("vision.qa.failed", error=str(exc))
        return ""

