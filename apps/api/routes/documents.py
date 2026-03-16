from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from persistence.document_repository import DocumentRepository
from storage.db.db import get_db


router = APIRouter(prefix="/documents", tags=["documents"])


def _estimate_tokens(text_value: str) -> int:
    # Heuristic: ~4 chars per token (varies by language/model).
    s = str(text_value or "")
    if not s:
        return 0
    return max(1, int(math.ceil(len(s) / 4)))


class BatchRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)
    include_content: bool = False
    max_content_chars: int = 2000


@router.post("/batch")
async def documents_batch(
    req: BatchRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    ids = [str(i or "").strip() for i in (req.ids or []) if str(i or "").strip()]
    # Deduplicate while preserving order.
    seen: set[str] = set()
    doc_ids: list[str] = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        doc_ids.append(i)

    if not doc_ids:
        return {"documents": []}
    if len(doc_ids) > 60:
        raise HTTPException(status_code=400, detail="Too many ids (max 60).")

    docs = await DocumentRepository(session).get_by_ids(doc_ids)
    by_id = {str(d.get("id") or ""): d for d in docs or []}

    out: list[dict[str, Any]] = []
    max_chars = max(200, min(int(req.max_content_chars or 2000), 20000))
    for doc_id in doc_ids:
        d = by_id.get(doc_id)
        if not d:
            continue
        content = str(d.get("content") or "")
        payload: dict[str, Any] = {
            "id": str(d.get("id") or ""),
            "title": str(d.get("title") or ""),
            "source": str(d.get("source") or ""),
            "url": str(d.get("url") or ""),
            "author": str(d.get("author") or ""),
            "updated_at": d.get("updated_at"),
            "content_len": len(content),
            "token_estimate": _estimate_tokens(content),
            "snippet": content[:420],
        }
        if req.include_content:
            payload["content"] = content[:max_chars]
        out.append(payload)

    return {"documents": out}


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    doc_id = str(document_id or "").strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="Missing document_id.")
    docs = await DocumentRepository(session).get_by_ids([doc_id])
    if not docs:
        raise HTTPException(status_code=404, detail="Document not found.")
    d = docs[0]
    content = str(d.get("content") or "")
    return {
        "document": {
            "id": str(d.get("id") or ""),
            "title": str(d.get("title") or ""),
            "source": str(d.get("source") or ""),
            "url": str(d.get("url") or ""),
            "author": str(d.get("author") or ""),
            "updated_at": d.get("updated_at"),
            "content_len": len(content),
            "token_estimate": _estimate_tokens(content),
            "content": content[:12000],
        }
    }

