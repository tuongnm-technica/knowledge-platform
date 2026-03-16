from __future__ import annotations

import re
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from orchestration.agent import OllamaLLM
from persistence.doc_draft_repository import DocDraftRepository
from persistence.document_repository import DocumentRepository
from prompts.doc_draft_prompt import SUPPORTED_DOC_TYPES, build_doc_system_prompt, build_doc_user_prompt
from storage.db.db import get_db


log = structlog.get_logger()
router = APIRouter(prefix="/docs", tags=["docs"])


class FromAnswerRequest(BaseModel):
    doc_type: str = Field(default="srs", max_length=50)
    question: str = Field(default="", max_length=5000)
    answer: str = Field(default="", max_length=20000)
    sources: list[dict] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=255)


class DraftUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None


def _extract_doc_ids(sources: list[dict]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for s in sources or []:
        doc_id = str((s or {}).get("document_id") or "").strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        ids.append(doc_id)
    return ids


def _default_title(doc_type: str, question: str) -> str:
    label = SUPPORTED_DOC_TYPES.get(doc_type, doc_type).split("(", 1)[0].strip()
    q = re.sub(r"\s+", " ", str(question or "").strip())
    q = q[:80] if q else "Draft"
    return f"{label} Draft — {q}" if q and q != "Draft" else f"{label} Draft"


def _fallback_doc(*, doc_type: str, title: str, question: str, sources: list[dict]) -> str:
    lines: list[str] = []
    lines.append(f"# {title}".strip())
    lines.append("")
    lines.append(f"_doc_type: `{doc_type}`_")
    lines.append("")
    lines.append("## Context")
    lines.append(question.strip() or "TBD")
    lines.append("")
    lines.append("## Draft")
    lines.append("- TBD")
    lines.append("")
    lines.append("## Open questions")
    lines.append("- TBD")
    lines.append("")
    lines.append("## Sources")
    for s in (sources or [])[:12]:
        lines.append(f"- [{s.get('source','')}] {s.get('title','')} {s.get('url','')}".strip())
    lines.append("")
    return "\n".join(lines).strip() + "\n"


@router.post("/drafts/from-answer")
async def create_doc_draft_from_answer(
    req: FromAnswerRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    doc_type = (req.doc_type or "srs").strip().lower()
    if doc_type not in SUPPORTED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported doc_type: {doc_type}")

    doc_ids = _extract_doc_ids(req.sources)
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No document sources found in this answer.")

    docs = await DocumentRepository(session).get_by_ids(doc_ids[:12])
    if not docs:
        raise HTTPException(status_code=404, detail="Referenced documents are not available in the database.")

    title = (req.title or "").strip() or _default_title(doc_type, req.question)

    system = build_doc_system_prompt(doc_type=doc_type)
    user = build_doc_user_prompt(
        doc_type=doc_type,
        question=req.question or "",
        answer=req.answer or "",
        sources=[dict(s) for s in (req.sources or [])[:12]],
        documents=docs,
    )

    content = ""
    llm = OllamaLLM()
    try:
        ok = await llm.is_available()
    except Exception:
        ok = False

    if ok:
        try:
            content = await llm.chat(system=system, user=user, max_tokens=1800)
        except Exception as exc:
            log.error("docs.draft.llm_failed", doc_type=doc_type, error=str(exc))
            content = ""

    if not content:
        content = _fallback_doc(doc_type=doc_type, title=title, question=req.question or "", sources=req.sources or [])

    snapshot = {
        "created_at": datetime.utcnow().isoformat(),
        "doc_type": doc_type,
        "sources": [dict(s) for s in (req.sources or [])[:12]],
    }
    draft = await DocDraftRepository(session).create(
        doc_type=doc_type,
        title=title,
        content=content,
        source_document_ids=doc_ids[:12],
        source_snapshot=snapshot,
        created_by=current_user.user_id,
        question=req.question or "",
        answer=req.answer or "",
    )
    return {"draft": draft, "supported_doc_types": SUPPORTED_DOC_TYPES}


@router.get("/drafts/{draft_id}")
async def get_doc_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    draft = await DocDraftRepository(session).get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return {"draft": draft, "viewer": {"user_id": current_user.user_id}, "supported_doc_types": SUPPORTED_DOC_TYPES}


@router.put("/drafts/{draft_id}")
async def update_doc_draft(
    draft_id: str,
    req: DraftUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    draft = await DocDraftRepository(session).update(
        draft_id,
        title=req.title,
        content=req.content,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return {"draft": draft}

