import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import (
    CurrentUser,
    require_admin,
)
from storage.db.db import get_db

router = APIRouter(prefix="/groups", tags=["groups"])

@router.get("")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    result = await db.execute(text("SELECT id, name FROM groups ORDER BY name"))
    return [dict(row) for row in result.mappings().all()]

class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    id: str | None = Field(default=None, max_length=255)

class GroupUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class GroupOverrideRequest(BaseModel):
    group_id: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=2000)

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group_admin(
    req: GroupCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    group_id = _make_group_id(req.name, req.id)
    existing = await db.execute(
        text("SELECT 1 FROM groups WHERE id = :id"),
        {"id": group_id},
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Group da ton tai")

    await db.execute(
        text("INSERT INTO groups (id, name) VALUES (:id, :name)"),
        {"id": group_id, "name": req.name.strip()},
    )
    await db.commit()
    return {"status": "created", "group_id": group_id}

@router.patch("/{group_id}")
async def update_group_admin(
    group_id: str,
    req: GroupUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    result = await db.execute(
        text("UPDATE groups SET name = :name WHERE id = :id"),
        {"id": group_id, "name": req.name.strip()},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group khong ton tai")
    await db.commit()
    return {"status": "updated", "group_id": group_id}

def _make_group_id(name: str, custom_id: str | None = None) -> str:
    raw = custom_id or name
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    if not slug:
        raise HTTPException(status_code=400, detail="Group id khong hop le")
    return slug if slug.startswith("group_") else f"group_{slug}"

async def validate_group_ids(db: AsyncSession, group_ids: list[str]) -> list[str]:
    cleaned = [group_id.strip() for group_id in group_ids if group_id and group_id.strip()]
    if not cleaned:
        return []

    result = await db.execute(
        text("SELECT id FROM groups WHERE id = ANY(:group_ids)"),
        {"group_ids": cleaned},
    )
    found = {row[0] for row in result.fetchall()}
    missing = sorted(set(cleaned) - found)
    if missing:
        raise HTTPException(status_code=400, detail=f"Group khong ton tai: {', '.join(missing)}")
    return cleaned
