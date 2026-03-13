"""
apps/api/routes/tasks.py
REST API cho Phase 3 Auto Task Creator.

Endpoints:
  GET  /tasks              → danh sách drafts (pending)
  GET  /tasks/count        → số lượng pending (cho badge UI)
  POST /tasks/scan         → manual trigger scan Slack + Confluence
  POST /tasks/{id}/confirm → confirm draft (có thể edit trước)
  POST /tasks/{id}/reject  → reject draft
  POST /tasks/{id}/submit  → submit confirmed draft lên Jira thật
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from tasks.repository import TaskDraftRepository
from tasks.scanner import scan_and_create_drafts
from tasks.jira_creator import submit_to_jira
from apps.api.auth.dependencies import get_current_user, CurrentUser
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/tasks", tags=["tasks"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    slack_days:       int = 1
    confluence_days:  int = 1


class ConfirmRequest(BaseModel):
    title:              Optional[str] = None
    description:        Optional[str] = None
    suggested_assignee: Optional[str] = None
    priority:           Optional[str] = None
    jira_project:       Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Trả về số lượng pending drafts — dùng cho badge trên sidebar."""
    repo  = TaskDraftRepository(db)
    count = await repo.count_pending()
    return {"count": count}


@router.get("")
async def list_drafts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Danh sách tất cả pending drafts."""
    repo   = TaskDraftRepository(db)
    drafts = await repo.get_pending()
    return {
        "drafts": [_format_draft(d) for d in drafts],
        "count":  len(drafts),
    }


@router.post("/scan")
async def trigger_scan(
    req: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Manual trigger: quét Slack + Confluence và tạo draft tasks.
    Chạy background — không block.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as _AS
    from sqlalchemy.orm import sessionmaker
    from config.settings import settings as _s

    async def _bg_scan():
        engine  = create_async_engine(_s.DATABASE_URL)
        Session = sessionmaker(engine, class_=_AS, expire_on_commit=False)
        async with Session() as session:
            stats = await scan_and_create_drafts(
                session=session,
                triggered_by="manual",
                created_by=current_user.user_id,
                slack_days=req.slack_days,
                confluence_days=req.confluence_days,
            )
            log.info("tasks.scan.done", user=current_user.user_id, **stats)

    background_tasks.add_task(_bg_scan)
    return {
        "message": f"Đang quét Slack ({req.slack_days} ngày) + Confluence ({req.confluence_days} ngày)...",
        "status":  "scanning",
    }


@router.post("/{draft_id}/confirm")
async def confirm_draft(
    draft_id: str,
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """User confirm draft (có thể edit trước khi confirm)."""
    repo = TaskDraftRepository(db)
    ok   = await repo.confirm(
        draft_id=draft_id,
        user_id=current_user.user_id,
        updates=req.model_dump(exclude_none=True),
    )
    if not ok:
        raise HTTPException(404, "Draft không tồn tại hoặc đã được xử lý")
    return {"message": "Đã confirm. Bấm Submit để tạo Jira task.", "draft_id": draft_id}


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """User reject/xóa draft."""
    repo = TaskDraftRepository(db)
    ok   = await repo.reject(draft_id, current_user.user_id)
    if not ok:
        raise HTTPException(404, "Draft không tồn tại hoặc đã được xử lý")
    return {"message": "Đã reject draft.", "draft_id": draft_id}


@router.post("/{draft_id}/submit")
async def submit_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Submit confirmed draft lên Jira thật."""
    repo  = TaskDraftRepository(db)
    draft = await repo.get_by_id(draft_id)

    if not draft:
        raise HTTPException(404, "Draft không tồn tại")
    if draft["status"] not in ("pending", "confirmed"):
        raise HTTPException(400, f"Draft đã ở trạng thái '{draft['status']}', không thể submit")

    jira_key = await submit_to_jira(
        project     = draft.get("jira_project") or "ECOS2025",
        title       = draft["title"],
        description = draft.get("description") or draft["title"],
        assignee    = draft.get("suggested_assignee"),
        priority    = draft.get("priority") or "Medium",
        labels      = draft.get("labels") or [],
    )

    if not jira_key:
        raise HTTPException(502, "Không thể tạo Jira task. Kiểm tra kết nối Jira.")

    await repo.mark_submitted(draft_id, jira_key)
    return {
        "message":  f"Đã tạo Jira task thành công!",
        "jira_key": jira_key,
        "jira_url": f"{_jira_url()}/browse/{jira_key}",
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _format_draft(d: dict) -> dict:
    return {
        "id":                 str(d["id"]),
        "title":              d["title"],
        "description":        d.get("description") or "",
        "source_type":        d["source_type"],
        "source_ref":         d.get("source_ref") or "",
        "source_summary":     d.get("source_summary") or "",
        "suggested_assignee": d.get("suggested_assignee") or "",
        "priority":           d.get("priority") or "Medium",
        "labels":             d.get("labels") or [],
        "status":             d["status"],
        "triggered_by":       d.get("triggered_by") or "scheduler",
        "jira_project":       d.get("jira_project") or "ECOS2025",
        "created_at":         d["created_at"].isoformat() if d.get("created_at") else "",
    }


def _jira_url() -> str:
    from config.settings import settings
    return settings.JIRA_URL or "http://jira.technica.vn"

"""
Paste đoạn này vào cuối tasks/routes.py (trước def _format_draft)
để debug scanner — xem raw content từ Slack trước khi LLM xử lý.
"""

@router.post("/scan-debug")
async def scan_debug(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Debug: chạy scan sync + trả về raw data để xem LLM nhận được gì."""
    import traceback as tb_module
    from config.settings import settings
    import httpx
    from datetime import datetime, timedelta, timezone

    result = {"channels": [], "errors": []}

    try:
        headers  = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
        oldest   = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

        async with httpx.AsyncClient(timeout=15) as client:
            # List channels
            r = await client.get(
                "https://slack.com/api/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": 50},
            )
            channels = [c for c in r.json().get("channels", []) if not c.get("is_archived")]

            for ch in channels[:10]:  # check 10 channels
                ch_id   = ch["id"]
                ch_name = ch.get("name", ch_id)

                r2 = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={"channel": ch_id, "oldest": str(oldest), "limit": 50},
                )
                msgs = [
                    m.get("text", "") for m in r2.json().get("messages", [])
                    if m.get("type") == "message" and m.get("text")
                ]
                content = "\n".join(msgs)
                result["channels"].append({
                    "name":          ch_name,
                    "id":            ch_id,
                    "message_count": len(msgs),
                    "content_len":   len(content),
                    "preview":       content[:200] if content else "(empty)",
                    "will_extract":  len(content) >= 50,
                })

    except Exception as e:
        result["errors"].append({"error": str(e), "trace": tb_module.format_exc()})

    return result