from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from config.settings import settings
from permissions.filter import PermissionFilter
from persistence.asset_repository import AssetRepository
from storage.db.db import get_db


router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/{asset_id}")
async def get_asset_file(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    asset = await AssetRepository(session).get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    doc_id = str(asset.get("document_id") or "").strip()
    if not doc_id:
        raise HTTPException(status_code=404, detail="Asset has no document")

    allowed = await PermissionFilter(session).allowed_docs(current_user.user_id)
    if allowed is not None and doc_id not in set(str(x) for x in allowed):
        raise HTTPException(status_code=403, detail="Forbidden")

    rel_path = str(asset.get("local_path") or "").strip().replace("\\", "/")
    if not rel_path:
        raise HTTPException(status_code=404, detail="Asset is missing path")

    base = Path(settings.ASSETS_DIR or "assets")
    abs_path = (base / rel_path).resolve()
    # Basic traversal guard: ensure file is inside assets root.
    try:
        abs_path.relative_to(base.resolve())
    except Exception:
        raise HTTPException(status_code=404, detail="Asset path invalid")

    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Asset file missing")

    media_type = str(asset.get("mime_type") or "").strip() or None
    filename = str(asset.get("filename") or "").strip() or None
    return FileResponse(path=str(abs_path), media_type=media_type, filename=filename)

