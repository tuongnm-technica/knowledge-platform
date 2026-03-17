"""
tasks/extractor.py
Dùng Ollama LLM để extract action items từ Slack messages / Confluence pages.
Output: danh sách ExtractedTask (JSON).
"""
from __future__ import annotations

import json
import re
import structlog
from tasks.models import ExtractedTask
from llm.base import ILLMClient
from prompts.extractor_prompt import EXTRACT_SYSTEM

log = structlog.get_logger()


async def extract_tasks_from_content(
    content: str,
    source_type: str,
    llm_client: ILLMClient,
    source_ref: str = "",
) -> list[ExtractedTask]:
    """
    Gọi Ollama để extract action items từ content.
    Trả về list ExtractedTask (có thể rỗng).
    """
    if not content or len(content.strip()) < 50:
        return []

    # Truncate để tránh context quá dài
    truncated = content[:4000]

    prompt = (
        f"Nguồn: {source_type.upper()} — {source_ref}\n\n"
        f"Nội dung:\n{truncated}\n\n"
        "Hãy extract tất cả action items từ nội dung trên:"
    )

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            raw = await llm_client.chat(
                system=EXTRACT_SYSTEM,
                user=prompt,
                max_tokens=800,
            )

            tasks = _parse_tasks(raw)
            log.info("extractor.done", source=source_type, ref=source_ref, found=len(tasks))
            return tasks

        except Exception as e:
            log.error("extractor.error_final", source=source_type, error=str(e), attempt=attempt)
            if attempt >= max_retries:
                return []


def _parse_tasks(raw: str) -> list[ExtractedTask]:
    """Parse JSON output từ LLM — robust với các format LLM hay sinh ra."""
    # Strip markdown code blocks
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Tìm JSON object
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        log.debug("extractor.parse_failed.no_json_found", raw=raw[:200])
        return []

    try:
        data = json.loads(m.group(0))
        tasks = []
        for item in data.get("tasks", []):
            if not item.get("title"):
                continue
            try:
                tasks.append(ExtractedTask(
                    title=item["title"].strip(),
                    description=item.get("description", "").strip(),
                    suggested_assignee=item.get("suggested_assignee") or None,
                    priority=item.get("priority", "Medium"),
                    labels=item.get("labels", []),
                    evidence_ts=str(item.get("evidence_ts") or "").strip() or None,
                    evidence=str(item.get("evidence") or "").strip() or None,
                ))
            except Exception as e:
                log.debug("extractor.parse_item_failed", error=str(e), item=item)
                continue
        return tasks
    except (json.JSONDecodeError, KeyError) as e:
        log.error("extractor.parse_failed.invalid_json", error=str(e))
        return []
