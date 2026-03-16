from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from config.settings import settings
from orchestration.agent import OllamaLLM
from persistence.document_repository import DocumentRepository
from persistence.srs_draft_repository import SRSDraftRepository
from prompts.srs_draft_prompt import build_srs_system_prompt, build_srs_user_prompt
from storage.db.db import get_db


log = structlog.get_logger()
router = APIRouter(prefix="/srs", tags=["srs"])


class FromAnswerRequest(BaseModel):
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


def _default_title(question: str) -> str:
    q = re.sub(r"\s+", " ", str(question or "").strip())
    q = q[:80] if q else "SRS Draft"
    return f"SRS Draft — {q}" if q and q != "SRS Draft" else "SRS Draft"


def _fallback_srs(
    *,
    title: str,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append(f"# {title}".strip())
    lines.append("")
    lines.append("## 0. Glossary")
    lines.append("| Thuật ngữ | Định nghĩa | Ví dụ | Không nhầm với |")
    lines.append("|---|---|---|---|")
    lines.append("| TBD | TBD | TBD | TBD |")
    lines.append("")
    lines.append("## 1. Giới thiệu")
    lines.append(f"- Yêu cầu: {question.strip() or 'TBD'}")
    lines.append("")
    lines.append("## 2. Tổng quan giải pháp")
    lines.append(answer.strip() or "TBD")
    lines.append("")
    lines.append("## 3. Business Rules (BR-xx)")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 4. Functional Requirements (FR-xx)")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 5. Non-Functional Requirements (NFR-xx)")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 6. Data Model (high-level)")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 7. API Specification (high-level)")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 8. UI/UX Notes")
    lines.append("- TBD")
    lines.append("")
    lines.append("## 9. Traceability + Open Questions")
    lines.append("### Traceability Matrix")
    lines.append("| FR | UC | VR | TC |")
    lines.append("|---|---|---|---|")
    lines.append("| TBD | TBD | TBD | TBD |")
    lines.append("")
    lines.append("### Open questions")
    lines.append("- TBD")
    lines.append("")
    lines.append("### Sources")
    for s in (sources or [])[:12]:
        lines.append(f"- [{s.get('source','')}] {s.get('title','')} {s.get('url','')}".strip())
    lines.append("")
    return "\n".join(lines).strip() + "\n"


@router.post("/drafts/from-answer")
async def create_srs_draft_from_answer(
    req: FromAnswerRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    doc_ids = _extract_doc_ids(req.sources)
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No document sources found in this answer.")

    # Fetch documents (for condensed context).
    docs = await DocumentRepository(session).get_by_ids(doc_ids[:12])
    if not docs:
        raise HTTPException(status_code=404, detail="Referenced documents are not available in the database.")

    title = (req.title or "").strip() or _default_title(req.question)

    # Build prompt.
    system = build_srs_system_prompt()
    user = build_srs_user_prompt(
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
            log.error("srs.draft.llm_failed", error=str(exc))
            content = ""

    if not content:
        content = _fallback_srs(
            title=title,
            question=req.question or "",
            answer=req.answer or "",
            sources=[dict(s) for s in (req.sources or [])[:12]],
        )

    # Persist draft.
    snapshot = {
        "created_at": datetime.utcnow().isoformat(),
        "sources": [dict(s) for s in (req.sources or [])[:12]],
    }
    draft = await SRSDraftRepository(session).create(
        title=title,
        content=content,
        source_document_ids=doc_ids[:12],
        source_snapshot=snapshot,
        created_by=current_user.user_id,
        question=req.question or "",
        answer=req.answer or "",
    )
    return {"draft": draft}


@router.get("/drafts/{draft_id}")
async def get_srs_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    draft = await SRSDraftRepository(session).get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    # MVP: any authenticated user can open. Future: enforce created_by / group access.
    return {"draft": draft, "viewer": {"user_id": current_user.user_id}}


@router.put("/drafts/{draft_id}")
async def update_srs_draft(
    draft_id: str,
    req: DraftUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    draft = await SRSDraftRepository(session).update(
        draft_id,
        title=req.title,
        content=req.content,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return {"draft": draft}

