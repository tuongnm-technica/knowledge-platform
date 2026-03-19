from __future__ import annotations

import json
import re
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from services.llm_service import LLMService
from persistence.doc_draft_repository import DocDraftRepository
from persistence.document_repository import DocumentRepository
from persistence.project_memory_repository import ProjectMemoryRepository
from prompts.doc_draft_prompt import SUPPORTED_DOC_TYPES, build_doc_system_prompt, build_doc_user_prompt
from storage.db.db import get_db
from orchestration.agent import OllamaLLM


log = structlog.get_logger()
router = APIRouter(prefix="/docs", tags=["docs"])


class FromAnswerRequest(BaseModel):
    doc_type: str = Field(default="srs", max_length=50)
    question: str = Field(default="", max_length=5000)
    answer: str = Field(default="", max_length=20000)
    sources: list[dict] = Field(default_factory=list)
    title: str | None = Field(default=None, max_length=255)


class FromDocumentsRequest(BaseModel):
    doc_type: str = Field(default="srs", max_length=50)
    doc_ids: list[str] = Field(default_factory=list)
    goal: str = Field(default="", max_length=5000)
    title: str | None = Field(default=None, max_length=255)


class DraftUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    status: str | None = Field(default=None, max_length=30)


class DraftRefineRequest(BaseModel):
    selected_text: str = Field(..., max_length=15000)
    instruction: str = Field(..., max_length=1000)


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


def _doc_sources_from_documents(docs: list[dict]) -> list[dict]:
    sources: list[dict] = []
    for d in docs or []:
        doc_id = str(d.get("id") or "").strip()
        if not doc_id:
            continue
        content = str(d.get("content") or "").strip()
        sources.append(
            {
                "document_id": doc_id,
                "title": str(d.get("title") or "").strip(),
                "url": str(d.get("url") or "").strip(),
                "source": str(d.get("source") or "").strip(),
                "snippet": content[:320],
            }
        )
    return sources


def _dedupe_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values or []:
        s = str(v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _parse_llm_response(text: str) -> tuple[str, dict]:
    """Parse the LLM response to separate Markdown content and JSON structured data."""
    text = text or ""
    structured_data = {}
    
    match = re.search(r"<json>\s*(.*?)\s*</json>", text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1)
        
        # Dọn dẹp lỗi phổ biến của AI: bọc thêm markdown ```json ... ``` bên trong thẻ <json>
        json_str = re.sub(r"^```(?:json)?|```$", "", json_str.strip(), flags=re.MULTILINE).strip()
        
        try:
            structured_data = json.loads(json_str)
        except Exception as e:
            log.warning("docs.draft.parse_json_error", error=str(e), snippet=json_str[:100])
        
        content = text[:match.start()] + text[match.end():]
        content = content.strip()
    else:
        content = text.strip()
        
    return content, structured_data


def _build_memory_prompt(memory_grouped: dict) -> str:
    if not memory_grouped:
        return ""
    
    lines = [
        "\n\n--- PROJECT MEMORY ---",
        "You MUST adhere to these previously defined concepts and roles. Do not redefine them differently."
    ]
    
    for mtype, items in memory_grouped.items():
        lines.append(f"\n## {mtype.upper()}:")
        # Giới hạn 50 items mỗi loại, cắt ngắn content để tránh nổ token
        for item in items[:50]:
            key = str(item.get("key") or "").strip()
            content = str(item.get("content") or "").strip()[:400]
            if key and content:
                lines.append(f"- {key}: {content}")
    
    lines.append("------------------------\n")
    return "\n".join(lines)


async def _extract_and_save_memory(structured_data: dict, repo: ProjectMemoryRepository, user_id: str):
    if not structured_data:
        return
        
    # 1. Trích xuất Glossary
    for item in structured_data.get("glossary", []):
        if isinstance(item, dict):
            k = item.get("term")
            v = item.get("definition")
            if k and v:
                await repo.upsert(memory_type="glossary", key=k[:255], content=v[:1000], created_by=user_id)
                
    # 2. Trích xuất Stakeholders / Actors (Tương thích chuẩn JSON Schema mới)
    stakeholders = structured_data.get("stakeholders") or structured_data.get("actors") or []
    for item in stakeholders:
        if isinstance(item, dict):
            k = item.get("name") or item.get("actor")
            v = item.get("role") or item.get("description")
            if k and v:
                await repo.upsert(memory_type="actor", key=k[:255], content=v[:1000], created_by=user_id)

    # 3. Trích xuất Business Rules (Dự phòng nếu AI có sinh ra field này)
    rules = structured_data.get("business_rules") or structured_data.get("rules") or []
    for item in rules:
        if isinstance(item, dict):
            k = item.get("id") or item.get("rule")
            v = item.get("description") or item.get("desc")
            if k and v:
                await repo.upsert(memory_type="rule", key=k[:255], content=v[:1000], created_by=user_id)


@router.get("/supported-types")
async def get_supported_doc_types(
    _: CurrentUser = Depends(get_current_user),
):
    """Return list of supported document types for frontend."""
    return {"supported_types": SUPPORTED_DOC_TYPES}


@router.get("/skills")
async def get_skill_agents(
    _: CurrentUser = Depends(get_current_user),
):
    """Return mygpt-ba skill agents metadata for the Skill Selector UI."""
    from prompts.doc_draft_prompt import SKILL_AGENT_LABELS, SKILL_DOC_TYPE_GROUPS
    agents = [
        {
            "doc_type": doc_type,
            "label": label,
            "description": desc,
        }
        for doc_type, (label, desc) in SKILL_AGENT_LABELS.items()
    ]
    return {"agents": agents, "groups": SKILL_DOC_TYPE_GROUPS}


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
    system += "\n\nCRITICAL REQUIREMENT: You MUST output a structured JSON representing the core data of your response. Place this JSON anywhere in your response wrapped exactly in <json> and </json> tags."

    memory_grouped = await ProjectMemoryRepository(session).get_all_grouped()
    system += _build_memory_prompt(memory_grouped)

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

    structured_data = {}
    if ok:
        try:
            from orchestration.doc_orchestrator import DocOrchestrator
            orchestrator = DocOrchestrator(llm)
            raw_content = await orchestrator.generate_document_pipeline(system=system, user=user, max_tokens=1800)
            content, structured_data = _parse_llm_response(raw_content)
            if structured_data:
                repo = ProjectMemoryRepository(session)
                await _extract_and_save_memory(structured_data, repo, current_user.user_id)
        except Exception as exc:
            log.error("docs.draft.llm_failed", doc_type=doc_type, error=str(exc))
            content = ""
            structured_data = {}

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
        structured_data=structured_data,
        source_document_ids=doc_ids[:12],
        source_snapshot=snapshot,
        created_by=current_user.user_id,
        question=req.question or "",
        answer=req.answer or "",
    )
    return {"draft": draft, "supported_doc_types": SUPPORTED_DOC_TYPES}


@router.post("/drafts/from-documents")
async def create_doc_draft_from_documents(
    req: FromDocumentsRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    doc_type = (req.doc_type or "srs").strip().lower()
    if doc_type not in SUPPORTED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported doc_type: {doc_type}")

    doc_ids = _dedupe_ids(req.doc_ids)
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No documents selected.")
    if len(doc_ids) > 12:
        raise HTTPException(status_code=400, detail="Too many documents selected (max 12).")

    docs = await DocumentRepository(session).get_by_ids(doc_ids)
    if not docs:
        raise HTTPException(status_code=404, detail="Selected documents are not available in the database.")

    sources = _doc_sources_from_documents(docs)
    title = (req.title or "").strip() or _default_title(doc_type, req.goal)

    # Load possibly-customised prompt from DB; fall back to hardcoded default
    from persistence.skill_prompt_repository import SkillPromptRepository
    db_row = await SkillPromptRepository(session).get(doc_type)
    db_prompt: str | None = db_row["system_prompt"] if db_row else None

    system = build_doc_system_prompt(doc_type=doc_type, db_prompt=db_prompt)
    system += "\n\nCRITICAL REQUIREMENT: You MUST output a structured JSON representing the core data of your response. Place this JSON anywhere in your response wrapped exactly in <json> and </json> tags."

    memory_grouped = await ProjectMemoryRepository(session).get_all_grouped()
    system += _build_memory_prompt(memory_grouped)

    user = build_doc_user_prompt(
        doc_type=doc_type,
        question=req.goal or "",
        answer="",
        sources=sources[:12],
        documents=docs[:12],
    )

    content = ""
    llm = OllamaLLM()
    try:
        ok = await llm.is_available()
    except Exception:
        ok = False

    structured_data = {}
    if ok:
        try:
            from orchestration.doc_orchestrator import DocOrchestrator
            orchestrator = DocOrchestrator(llm)
            raw_content = await orchestrator.generate_document_pipeline(system=system, user=user, max_tokens=1800)
            content, structured_data = _parse_llm_response(raw_content)
            if structured_data:
                repo = ProjectMemoryRepository(session)
                await _extract_and_save_memory(structured_data, repo, current_user.user_id)
        except Exception as exc:
            log.error("docs.draft.llm_failed", doc_type=doc_type, error=str(exc))
            content = ""
            structured_data = {}

    if not content:
        content = _fallback_doc(doc_type=doc_type, title=title, question=req.goal or "", sources=sources[:12])

    snapshot = {
        "created_at": datetime.utcnow().isoformat(),
        "doc_type": doc_type,
        "source_document_ids": doc_ids,
        "sources": sources[:12],
    }
    draft = await DocDraftRepository(session).create(
        doc_type=doc_type,
        title=title,
        content=content,
        structured_data=structured_data,
        source_document_ids=doc_ids,
        source_snapshot=snapshot,
        created_by=current_user.user_id,
        question=req.goal or "",
        answer="",
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


@router.get("/drafts")
async def list_doc_drafts(
    limit: int = 50,
    doc_type: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # MVP: list only own drafts (admin can add a global list later).
    drafts = await DocDraftRepository(session).list_recent(
        created_by=current_user.user_id,
        limit=limit,
        doc_type=doc_type,
        status=status,
    )
    return {"drafts": drafts, "supported_doc_types": SUPPORTED_DOC_TYPES}


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
        status=req.status,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return {"draft": draft}


@router.delete("/drafts/{draft_id}")
async def delete_doc_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    ok = await DocDraftRepository(session).delete(
        draft_id,
        created_by=current_user.user_id,
        allow_any=bool(current_user.is_admin),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Draft not found (or not allowed).")
    return {"status": "deleted", "id": str(draft_id)}


@router.post("/drafts/{draft_id}/refine")
async def refine_draft_section(
    draft_id: str,
    req: DraftRefineRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    draft = await DocDraftRepository(session).get(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản nháp")

    system = """You are an AI Editing Assistant for a Business Analyst.
You are given a text snippet from a larger document, and an instruction from the user.
Your task is to rewrite ONLY the text snippet exactly according to the instruction.
Reply with the raw Markdown replacement text only. Do not add conversational padding like "Here is the rewritten text" or markdown block quotes if they aren't part of the text."""

    user_prompt = f"INSTRUCTION FROM USER: {req.instruction}\n\nORIGINAL SNIPPET TO REPLACE:\n{req.selected_text}"
    
    llm = OllamaLLM()
    try:
        ok = await llm.is_available()
        if not ok:
            raise HTTPException(status_code=503, detail="LLM hiện không khả dụng")
        new_text = await llm.chat(system=system, user=user_prompt, max_tokens=1500)
    except HTTPException:
        raise
    except Exception as e:
        log.error("docs.refine_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Lỗi khi chạy AI Rewrite")
        
    return {"refined_text": new_text.strip()}


# ── Project Memory API ────────────────────────────────────────────────────────

@router.get("/memory")
async def list_project_memory(
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    grouped = await ProjectMemoryRepository(session).get_all_grouped()
    return {"memory": grouped}


@router.delete("/memory/{memory_id}")
async def delete_project_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    ok = await ProjectMemoryRepository(session).delete(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy memory entry.")
    return {"status": "deleted", "id": memory_id}
