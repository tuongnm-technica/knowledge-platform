from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from persistence.skill_prompt_repository import SkillPromptRepository
from prompts.doc_draft_prompt import SKILL_SYSTEM_PROMPTS
from storage.db.db import get_db

router = APIRouter(prefix="/prompts", tags=["prompts"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


class PromptUpdateRequest(BaseModel):
    system_prompt: str


# ─── List all ─────────────────────────────────────────────────────────────────


@router.get("")
async def list_prompts(
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all skill prompts (label, description, doc_type, updated_at)."""
    repo = SkillPromptRepository(db)
    rows = await repo.list_all()
    return {"prompts": rows}


# ─── Get one ──────────────────────────────────────────────────────────────────


@router.get("/{doc_type}")
async def get_prompt(
    doc_type: str,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full system_prompt for a given doc_type."""
    repo = SkillPromptRepository(db)
    row = await repo.get(doc_type)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Prompt '{doc_type}' not found.")
    # Also expose the hardcoded default so the UI can show diff/reset
    default_prompt = SKILL_SYSTEM_PROMPTS.get(doc_type, "")
    return {**row, "default_prompt": default_prompt}


# ─── Update ───────────────────────────────────────────────────────────────────


@router.put("/{doc_type}")
async def update_prompt(
    doc_type: str,
    req: PromptUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the system_prompt for a given doc_type."""
    system_prompt = (req.system_prompt or "").strip()
    if not system_prompt:
        raise HTTPException(status_code=400, detail="system_prompt must not be empty.")

    repo = SkillPromptRepository(db)
    updated = await repo.update_prompt(
        doc_type=doc_type,
        system_prompt=system_prompt,
        updated_by=user.user_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Prompt '{doc_type}' not found.")
    return {"ok": True, "doc_type": doc_type}


# ─── Reset to default ─────────────────────────────────────────────────────────


@router.post("/{doc_type}/reset")
async def reset_prompt(
    doc_type: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset system_prompt to the hardcoded default."""
    repo = SkillPromptRepository(db)
    ok = await repo.reset_to_default(doc_type=doc_type, updated_by=user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Prompt '{doc_type}' not found or no default.")
    return {"ok": True, "doc_type": doc_type}
