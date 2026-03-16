from __future__ import annotations

import asyncio
import base64

import structlog

from config.settings import settings
from utils.ollama_api import ollama_chat


log = structlog.get_logger()


VISION_SYSTEM = """\
You are a vision assistant for enterprise knowledge ingestion.

Task:
- Describe the image content for semantic search and task extraction.
- Extract any visible text (OCR-like) when present.

Output requirements:
- Plain text only (no markdown).
- Keep it concise but information-dense.
"""


async def describe_image(
    *,
    image_bytes: bytes,
    hint: str = "",
    max_chars: int | None = None,
) -> str:
    if not settings.VISION_ENABLED:
        return ""
    model = str(settings.OLLAMA_VISION_MODEL or "").strip()
    if not model:
        return ""
    if not image_bytes:
        return ""

    prompt = "Describe this image and extract any visible text."
    if hint:
        prompt = f"{prompt}\nHint/context: {hint}".strip()

    b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        text = await ollama_chat(
            model=model,
            messages=[
                {"role": "system", "content": VISION_SYSTEM},
                {"role": "user", "content": prompt, "images": [b64]},
            ],
            options={"num_predict": 350, "temperature": 0.1},
            timeout=180,
        )
    except Exception as exc:
        log.warning("vision.describe.failed", error=str(exc))
        return ""

    limit = int(max_chars or settings.VISION_CAPTION_MAX_CHARS or 900)
    if limit > 50 and len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


async def describe_images_batch(
    items: list[dict],
    *,
    concurrency: int = 2,
) -> list[str]:
    """
    items: [{"image_bytes": bytes, "hint": str}]
    """
    if not items:
        return []
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def _one(item: dict) -> str:
        async with sem:
            return await describe_image(
                image_bytes=item.get("image_bytes") or b"",
                hint=str(item.get("hint") or "").strip(),
            )

    return await asyncio.gather(*[_one(item) for item in items])
