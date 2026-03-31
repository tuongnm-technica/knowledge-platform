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


async def detect_action_signal(content: str, llm_client: ILLMClient) -> bool:
    """Layer 3: Fast check if the content contains any actionable tasks/requests to save tokens."""
    sys_prompt = (
        "Bạn là AI classifier chuyên nghiệp. Phân tích nội dung chat và quyết định xem có chứa YÊU CẦU CÔNG VIỆC THỰC SỰ (Task, Bug, Feature) cần theo dõi lâu dài hay không.\n"
        "QUY TẮC:\n"
        "- Trả về has_action=true nếu là yêu cầu kỹ thuật, sửa lỗi, tính năng mới hoặc task có quy mô rõ ràng.\n"
        "- PHẢI trả về has_action=false nếu chỉ là: chào hỏi, nhờ vả nhanh (check log giúp em, ping bác, bác xem cái này...), thảo luận phi kỹ thuật, hoặc chỉ là câu cảm ơn.\n"
        "Trả về JSON: {\"has_action\": true/false, \"confidence\": 0.9}. CHỈ JSON."
    )
    try:
        raw = await llm_client.chat(system=sys_prompt, user=f"Nội dung:\n{content[:2000]}", max_tokens=60)
        return '"has_action": true' in raw.lower() or '"has_action":true' in raw.lower()
    except Exception as e:
        log.warning("extractor.signal.error", error=str(e))
        return True  # Fallback to extraction if signal check fails


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


def _parse_item(item: dict) -> ExtractedTask | None:
    if not item.get("title"):
        return None
    try:
        subtasks_raw = item.get("subtasks", [])
        parsed_subtasks = []
        if isinstance(subtasks_raw, list):
            for st in subtasks_raw:
                if isinstance(st, dict):
                    pst = _parse_item(st)
                    if pst:
                        parsed_subtasks.append(pst)
        
        return ExtractedTask(
            title=item["title"].strip(),
            description=item.get("description", "").strip(),
            suggested_assignee=item.get("suggested_assignee") or None,
            priority=item.get("priority", "Medium"),
            labels=item.get("labels", []),
            evidence_ts=str(item.get("evidence_ts") or "").strip() or None,
            evidence=str(item.get("evidence") or "").strip() or None,
            evidence_list=[str(x).strip() for x in item.get("evidence_list", []) if str(x).strip()],
            confidence=float(item.get("confidence", 0.0)),
            subtasks=parsed_subtasks
        )
    except Exception as e:
        log.debug("extractor.parse_item_failed", error=str(e), item=item)
        return None

def _parse_tasks(raw: str) -> list[ExtractedTask]:
    """Parse JSON output từ LLM — robust với các format LLM hay sinh ra."""
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        log.debug("extractor.parse_failed.no_json_found", raw=raw[:200])
        return []

    try:
        data = json.loads(m.group(0))
        tasks = []
        for item in data.get("tasks", []):
            task = _parse_item(item)
            if task:
                tasks.append(task)
        return tasks
    except (json.JSONDecodeError, KeyError) as e:
        log.error("extractor.parse_failed.invalid_json", error=str(e))
        return []
