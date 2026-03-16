from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from persistence.document_repository import DocumentRepository
from tasks.repository import TaskDraftRepository


log = structlog.get_logger()


TASK_SYSTEM = """\
Bạn là PM/Tech Lead. Nhiệm vụ: tạo 1 Jira task draft từ câu hỏi, câu trả lời và bằng chứng (evidence).

Yêu cầu:
- Trả về JSON THUẦN, không markdown.
- Không bịa thông tin ngoài CONTEXT. Nếu không đủ dữ liệu, hãy ghi rõ giả định trong description.
- title: ngắn, bắt đầu bằng động từ (Fix/Update/Investigate/Implement/Review...).
- description: Jira-ready, có sections:
  - Context
  - Proposed work
  - Acceptance criteria (bullet)
  - Evidence (links)
- labels: chọn từ [bug, feature, docs, review, deploy, meeting, followup] khi phù hợp, có thể rỗng.
- issue_type: chọn 1 trong [Task, Story, Bug, Epic]. Nếu không chắc, dùng Task.
- epic_key: nếu issue_type != Epic và context có nhắc tới epic (ví dụ "EPIC-123"), có thể set epic_key, không chắc thì null.
- components: mảng tên component nếu suy ra rõ ràng, không chắc thì để rỗng.
- due_date: YYYY-MM-DD nếu trong context có deadline rõ ràng, không chắc thì null.
- suggested_assignee: nếu có người phù hợp trong context, không chắc thì null.

Output JSON schema:
{
  "title": "...",
  "description": "...",
  "issue_type": "Task",
  "epic_key": null,
  "priority": "High|Medium|Low",
  "labels": ["bug"],
  "components": [],
  "due_date": null,
  "suggested_assignee": null
}
"""


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = re.sub(r"```(?:json)?|```", "", (raw or "").strip())
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        log.warning("task_writer.parse_json_failed", raw=m.group(0), error=str(exc))
        return {}
    except Exception as exc:
        log.warning("task_writer.parse_json_unexpected_error", raw=m.group(0), error=str(exc))
        return {}


def _safe_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


async def build_task_from_answer(
    *,
    session: AsyncSession,
    question: str,
    answer: str,
    sources: list[dict],
    created_by: str | None = None,
) -> dict:
    repo = TaskDraftRepository(session)
    doc_repo = DocumentRepository(session)

    # Best-effort: infer scope_group_id from the first source document permissions.
    scope_group_id: str | None = None
    try:
        doc_ids = [str(s.get("document_id") or "").strip() for s in (sources or []) if str(s.get("document_id") or "").strip()]
        doc_ids = list(dict.fromkeys(doc_ids))[:12]
        if doc_ids:
            rows = await doc_repo.get_by_ids(doc_ids)
            by_id = {str(r.get("id")): r for r in rows}
            for s in (sources or []):
                did = str(s.get("document_id") or "").strip()
                row = by_id.get(did)
                if not row:
                    continue
                perms = row.get("permissions") or []
                if isinstance(perms, str):
                    perms = []
                if isinstance(perms, list):
                    for p in perms:
                        pid = str(p or "").strip()
                        if pid.startswith("group_"):
                            scope_group_id = pid
                            break
                if scope_group_id:
                    break
    except Exception:
        scope_group_id = None

    # Build evidence list from sources (best-effort).
    evidence: list[dict] = []
    context_blocks: list[str] = []

    for s in (sources or [])[:6]:
        url = str(s.get("url") or "").strip()
        title = str(s.get("title") or "").strip()
        source = str(s.get("source") or "").strip()
        snippet = str(s.get("snippet") or s.get("quote") or s.get("content") or "").strip()
        document_id = str(s.get("document_id") or "").strip()
        chunk_id = str(s.get("chunk_id") or "").strip()

        quote = snippet[:600] if snippet else ""

        if chunk_id:
            try:
                neighbors = await doc_repo.get_neighbor_chunks(chunk_id, window=3)
                if neighbors:
                    joined = "\n".join([str(row["content"] or "") for row in neighbors])
                    joined = joined.strip()
                    if joined:
                        quote = joined[:2200]
            except Exception:
                pass

        if url or quote:
            evidence.append(
                {
                    "source": source,
                    "title": title,
                    "url": url,
                    "quote": quote,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                }
            )

        if quote:
            context_blocks.append(
                "\n".join(
                    [
                        f"SOURCE: {source}",
                        f"TITLE: {title}",
                        f"URL: {url}",
                        "QUOTE:",
                        quote,
                    ]
                ).strip()
            )

    context = "\n\n---\n\n".join(context_blocks)[:12000]

    user_prompt = "\n\n".join(
        [
            f"QUESTION:\n{question}".strip(),
            f"ANSWER:\n{answer}".strip(),
            "CONTEXT:",
            context or "(empty)",
        ]
    ).strip()

    title = (question or "").strip()
    description = (answer or "").strip()
    issue_type = "Task"
    epic_key: str | None = None
    priority = "Medium"
    labels: list[str] = []
    components: list[str] = []
    due_date: str | None = None
    suggested_assignee: str | None = None

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": TASK_SYSTEM},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"num_predict": 900, "temperature": 0.1},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()

        data = _parse_json_object(raw)
        if data.get("title"):
            title = str(data["title"]).strip()
        if data.get("description"):
            description = str(data["description"]).strip()
        if data.get("issue_type"):
            it = str(data.get("issue_type") or "").strip()
            if it in {"Task", "Story", "Bug", "Epic"}:
                issue_type = it
        epic_key = str(data.get("epic_key") or "").strip() or None
        if data.get("priority"):
            p = str(data.get("priority") or "").strip()
            if p in {"High", "Medium", "Low"}:
                priority = p
        labels = _safe_list(data.get("labels"))
        components = _safe_list(data.get("components"))
        due_date = str(data.get("due_date") or "").strip() or None
        suggested_assignee = str(data.get("suggested_assignee") or "").strip() or None

    except Exception as exc:
        log.warning("task_writer.llm_failed", error=str(exc))

    # Smart assignee suggestion (MVP): if LLM didn't propose, use historical patterns from previous drafts.
    if not suggested_assignee:
        try:
            suggested_assignee = await repo.suggest_assignee_from_history(labels=labels, components=components)
        except Exception:
            suggested_assignee = None

    # Ensure description contains evidence links even if LLM didn't include them.
    ev_lines = []
    for ev in evidence[:6]:
        if ev.get("url"):
            ev_lines.append(f"- {ev.get('source')}: {ev.get('url')}")
    if ev_lines:
        if "Evidence" not in description:
            description = (description + "\n\nEvidence:\n" + "\n".join(ev_lines)).strip()

    draft_id = await repo.create_draft(
        title=title or "Follow up",
        description=description or title or "Follow up",
        source_type="chat",
        source_ref=(question or "")[:200],
        source_summary=(answer or "")[:500],
        source_url="",
        scope_group_id=scope_group_id,
        source_meta={
            "question": question,
            "answer": (answer or "")[:2000],
        },
        evidence=evidence,
        issue_type=issue_type,
        epic_key=epic_key,
        suggested_assignee=suggested_assignee,
        priority=priority,
        labels=labels,
        components=components,
        due_date=due_date,
        suggested_fields={
            "issue_type": issue_type,
            "epic_key": epic_key,
            "labels": labels,
            "components": components,
            "due_date": due_date,
            "suggested_assignee": suggested_assignee,
        },
        triggered_by="chat",
        created_by=created_by,
    )

    return {
        "id": draft_id,
        "title": title,
        "description": description,
        "issue_type": issue_type,
        "epic_key": epic_key,
        "priority": priority,
        "labels": labels,
        "components": components,
        "due_date": due_date,
        "suggested_assignee": suggested_assignee,
        "evidence": evidence,
    }
