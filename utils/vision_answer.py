from __future__ import annotations

import base64

import structlog

from config.settings import settings
from utils.ollama_api import ollama_chat


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

    log.info("vision.qa.start", model=model, image_count=len(imgs_b64), context_chars=len(context or ""))
    try:
        return await ollama_chat(
            model=model,
            messages=[
                {"role": "system", "content": VISION_QA_SYSTEM},
                {"role": "user", "content": user_prompt, "images": imgs_b64},
            ],
            options={"num_predict": 700, "temperature": 0.1},
            timeout=240,
        )
    except Exception as exc:
        log.warning("vision.qa.failed", error=str(exc))
        return ""
