"""
tasks/extractor.py
Dùng Ollama LLM để extract action items từ Slack messages / Confluence pages.
Output: danh sách ExtractedTask (JSON).
"""
from __future__ import annotations
import json
import asyncio
import re
import structlog
from tasks.models import ExtractedTask
from config.settings import settings
from utils.ollama_api import ollama_chat

log = structlog.get_logger()

EXTRACT_SYSTEM = """\
Bạn là AI assistant phân tích nội dung cuộc họp và chat để tìm action items.

Nhiệm vụ: Đọc nội dung và extract TẤT CẢ các action items / công việc cần làm.

Quy tắc:
- Chỉ extract các task CỤ THỂ, có thể thực hiện được (actionable)
- Bỏ qua thảo luận chung, ý kiến, không có người thực hiện hoặc deadline
- Mỗi task phải có title rõ ràng (bắt đầu bằng động từ: Fix, Update, Review, Create, Deploy...)
- suggested_assignee: tên người được mention (@username) hoặc null
- priority: High nếu có từ "urgent/gấp/quan trọng", Low nếu "khi rảnh/nice to have", còn lại Medium
- labels: mảng tags phù hợp từ [bug, feature, docs, review, deploy, meeting, followup]
- evidence_ts: (Slack only, optional) nếu trong nội dung có dạng [HH:MM|<ts>] thì hãy lấy đúng <ts> (vd: 1710561234.567890)
- evidence: (optional) trích 1-2 dòng ngắn làm bằng chứng (ưu tiên dòng có [HH:MM|ts] nếu là Slack)

⚠️ Trả về JSON THUẦN TÚY — không markdown, không giải thích, chỉ JSON:
{"tasks": [{"title": "...", "description": "...", "suggested_assignee": "...", "priority": "Medium", "labels": ["bug"], "evidence_ts": "1710561234.567890", "evidence": "..."}]}

Nếu không có action item nào: {"tasks": []}
"""


async def extract_tasks_from_content(
    content: str,
    source_type: str,
    client,
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
            raw = await ollama_chat(
                model=settings.OLLAMA_LLM_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                options={"num_predict": 800, "temperature": 0.1},
                timeout=120,
            )

            tasks = _parse_tasks(raw)
            log.info("extractor.done", source=source_type, ref=source_ref, found=len(tasks))
            return tasks

        except Exception as e:
            log.warning("extractor.attempt_failed", source=source_type, attempt=attempt, error=str(e))
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s...
            else:
                log.error("extractor.error_final", source=source_type, error=str(e))
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
