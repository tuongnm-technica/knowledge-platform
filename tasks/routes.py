from datetime import date, datetime, timedelta, timezone

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from apps.api.auth.dependencies import CurrentUser, get_current_user, require_admin, require_task_manager
from config.settings import settings
from storage.db.db import get_db
from tasks.jira_creator import submit_to_jira
from tasks.jira_sync import sync_submitted_drafts
from tasks.grouping import group_drafts
from tasks.repository import TaskDraftRepository
from tasks.scanner import scan_and_create_drafts


log = structlog.get_logger()
router = APIRouter(prefix="/tasks", tags=["tasks"])


class ScanRequest(BaseModel):
    slack_days: int = 1
    confluence_days: int = 1


class ConfirmRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    suggested_assignee: str | None = None
    priority: str | None = None
    issue_type: str | None = None  # Task | Story | Bug | Epic
    epic_key: str | None = None
    labels: list[str] | None = None
    components: list[str] | None = None
    due_date: str | None = None  # YYYY-MM-DD
    jira_project: str | None = None


class BatchIdsRequest(BaseModel):
    ids: list[str]


class BatchUpdateRequest(BaseModel):
    ids: list[str]
    suggested_assignee: str | None = None
    priority: str | None = None
    issue_type: str | None = None
    epic_key: str | None = None
    jira_project: str | None = None
    labels: list[str] | None = None
    components: list[str] | None = None
    due_date: str | None = None  # YYYY-MM-DD


class FromAnswerRequest(BaseModel):
    question: str
    answer: str
    sources: list[dict] = []


async def _user_group_ids(db: AsyncSession, user_id: str) -> set[str]:
    result = await db.execute(
        text("""
            SELECT ug.group_id
            FROM user_groups ug
            WHERE ug.user_id = :uid
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_group_overrides ugo
                  WHERE ugo.user_id = ug.user_id
                    AND ugo.group_id = ug.group_id
                    AND COALESCE(ugo.effect, 'deny') = 'deny'
              )
        """),
        {"uid": user_id},
    )
    return {str(row[0]) for row in result.fetchall()}


async def _ensure_draft_scope_access(*, db: AsyncSession, draft_id: str, user: CurrentUser) -> dict:
    draft = await TaskDraftRepository(db).get_by_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft khong ton tai")

    if user.is_admin:
        return draft

    scope = str(draft.get("scope_group_id") or "").strip()
    if not scope:
        # Backward compatible: older drafts may not have scope assigned yet.
        return draft

    gids = await _user_group_ids(db, user.user_id)
    if scope not in gids:
        raise HTTPException(status_code=403, detail="Ban khong co quyen tren scope cua draft nay")
    return draft


@router.get("/count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Inbox count: pending + confirmed (not yet submitted).
    if current_user.is_admin:
        return {"count": await TaskDraftRepository(db).count_pending()}

    group_ids = sorted(await _user_group_ids(db, current_user.user_id))
    # If user has no scopes assigned, show 0 to avoid leaking drafts.
    if not group_ids:
        return {"count": 0}

    r = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM ai_task_drafts
            WHERE status IN ('pending', 'confirmed')
              AND (scope_group_id IS NULL OR scope_group_id = ANY(:gids))
            """
        ),
        {"gids": group_ids},
    )
    return {"count": int(r.scalar() or 0)}


@router.get("")
async def list_drafts(
    include_submitted: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = TaskDraftRepository(db)
    if include_submitted:
        rows = await repo.get_by_status(["pending", "confirmed", "submitted"])
    else:
        rows = await repo.get_open()

    if not current_user.is_admin:
        group_ids = await _user_group_ids(db, current_user.user_id)
        rows = [
            r
            for r in rows
            if not str(r.get("scope_group_id") or "").strip()
            or str(r.get("scope_group_id") or "").strip() in group_ids
        ]

    drafts = [_format_draft(draft) for draft in rows]
    drafts, groups = group_drafts(drafts)
    return {"drafts": drafts, "groups": groups, "count": len(drafts)}


@router.post("/scan")
async def trigger_scan(
    req: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    async def _bg_scan():
        engine = create_async_engine(settings.DATABASE_URL)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
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
        "message": f"Scanning Slack ({req.slack_days}d) and Confluence ({req.confluence_days}d).",
        "status": "scanning",
    }


@router.post("/{draft_id}/confirm")
async def confirm_draft(
    draft_id: str,
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    await _ensure_draft_scope_access(db=db, draft_id=draft_id, user=current_user)
    ok = await TaskDraftRepository(db).confirm(
        draft_id=draft_id,
        user_id=current_user.user_id,
        updates=req.model_dump(exclude_none=True),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Draft khong ton tai hoac da duoc xu ly")
    return {"message": "Draft confirmed.", "draft_id": draft_id}


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    await _ensure_draft_scope_access(db=db, draft_id=draft_id, user=current_user)
    ok = await TaskDraftRepository(db).reject(draft_id, current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Draft khong ton tai hoac da duoc xu ly")
    return {"message": "Draft rejected.", "draft_id": draft_id}


@router.post("/{draft_id}/submit")
async def submit_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    draft = await _ensure_draft_scope_access(db=db, draft_id=draft_id, user=current_user)
    if draft["status"] not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail=f"Draft dang o trang thai '{draft['status']}'")

    jira_project = draft.get("jira_project") or settings.DEFAULT_JIRA_PROJECT
    if not jira_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira project chua duoc cau hinh cho draft nay",
        )

    issue_type = (draft.get("issue_type") or "Task").strip() or "Task"
    epic_key = (draft.get("epic_key") or "").strip() or None

    jira_result = await submit_to_jira(
        project=jira_project,
        title=draft["title"],
        description=_build_jira_description(draft),
        assignee=draft.get("suggested_assignee"),
        priority=draft.get("priority") or "Medium",
        labels=draft.get("labels") or [],
        components=draft.get("components") or [],
        due_date=(draft.get("due_date") or None),
        issue_type=issue_type,
        epic_key=epic_key,
    )
    if not jira_result:
        raise HTTPException(status_code=502, detail="Khong the tao Jira task")

    jira_key = str(jira_result.get("key") or "").strip()
    if not jira_key:
        raise HTTPException(status_code=502, detail="Khong the tao Jira task")

    jira_meta = {
        "jira_assignee_account_id": jira_result.get("assignee_account_id"),
        "jira_issue_type": jira_result.get("issue_type"),
    }
    await TaskDraftRepository(db).mark_submitted(draft_id, jira_key, jira_meta=jira_meta)
    jira_base = settings.JIRA_URL.rstrip("/") if settings.JIRA_URL else ""
    return {
        "message": "Jira task created.",
        "jira_key": jira_key,
        "jira_url": f"{jira_base}/browse/{jira_key}" if jira_base else None,
    }


@router.post("/sync-jira-status")
async def manual_sync_jira_status(
    limit: int = 60,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    stats = await sync_submitted_drafts(db, limit=int(limit))
    return {"status": "ok", "stats": stats}


@router.post("/batch/confirm")
async def batch_confirm(
    req: BatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    repo = TaskDraftRepository(db)
    updated = 0
    for draft_id in req.ids:
        await _ensure_draft_scope_access(db=db, draft_id=str(draft_id), user=current_user)
        ok = await repo.confirm(
            draft_id=str(draft_id),
            user_id=current_user.user_id,
            updates=req.model_dump(exclude={"ids"}, exclude_none=True),
        )
        if ok:
            updated += 1
    return {"updated": updated}


@router.post("/batch/reject")
async def batch_reject(
    req: BatchIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = TaskDraftRepository(db)
    updated = 0
    for draft_id in req.ids:
        await _ensure_draft_scope_access(db=db, draft_id=str(draft_id), user=current_user)
        ok = await repo.reject(str(draft_id), current_user.user_id)
        if ok:
            updated += 1
    return {"updated": updated}


@router.post("/batch/update")
async def batch_update_fields(
    req: BatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    repo = TaskDraftRepository(db)
    updated = 0
    updates = req.model_dump(exclude={"ids"}, exclude_none=True)
    for draft_id in req.ids:
        await _ensure_draft_scope_access(db=db, draft_id=str(draft_id), user=current_user)
        ok = await repo.update_fields(str(draft_id), updates)
        if ok:
            updated += 1
    return {"updated": updated}


@router.post("/from-answer")
async def create_from_answer(
    req: FromAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager),
):
    from tasks.task_writer import build_task_from_answer

    draft = await build_task_from_answer(
        session=db,
        question=req.question,
        answer=req.answer,
        sources=req.sources or [],
        created_by=current_user.user_id,
    )
    return {"status": "created", "draft": draft}


def _format_draft(draft: dict) -> dict:
    due = draft.get("due_date")
    if due and hasattr(due, "isoformat"):
        due_value = due.isoformat()  # date/datetime
    else:
        due_value = str(due or "")
    jira_key = str(draft.get("jira_key") or "").strip()
    jira_base = settings.JIRA_URL.rstrip("/") if settings.JIRA_URL else ""

    return {
        "id": str(draft["id"]),
        "title": draft["title"],
        "description": draft.get("description") or "",
        "source_type": draft["source_type"],
        "source_ref": draft.get("source_ref") or "",
        "source_summary": draft.get("source_summary") or "",
        "source_url": draft.get("source_url") or "",
        "source_meta": draft.get("source_meta") or {},
        "evidence": draft.get("evidence") or [],
        "suggested_fields": draft.get("suggested_fields") or {},
        "issue_type": draft.get("issue_type") or "Task",
        "epic_key": draft.get("epic_key") or "",
        "suggested_assignee": draft.get("suggested_assignee") or "",
        "priority": draft.get("priority") or "Medium",
        "labels": draft.get("labels") or [],
        "components": draft.get("components") or [],
        "due_date": due_value,
        "status": draft["status"],
        "triggered_by": draft.get("triggered_by") or "scheduler",
        "jira_project": draft.get("jira_project") or settings.DEFAULT_JIRA_PROJECT or "",
        "created_at": draft["created_at"].isoformat() if draft.get("created_at") else "",
        "jira_key": draft.get("jira_key") or "",
        "jira_url": f"{jira_base}/browse/{jira_key}" if (jira_base and jira_key) else "",
        "submitted_at": draft.get("submitted_at").isoformat() if draft.get("submitted_at") else "",
        "confirmed_at": draft.get("confirmed_at").isoformat() if draft.get("confirmed_at") else "",
        "group_id": draft.get("group_id") or "",
        "scope_group_id": draft.get("scope_group_id") or "",
    }


def _build_jira_description(draft: dict) -> str:
    description = (draft.get("description") or "").strip() or (draft.get("title") or "").strip()
    source_url = (draft.get("source_url") or "").strip()
    source_ref = (draft.get("source_ref") or "").strip()

    # Best-effort: include evidence from source_meta if present.
    source_meta = draft.get("source_meta") or {}
    if isinstance(source_meta, str):
        try:
            import json
            source_meta = json.loads(source_meta) if source_meta else {}
        except Exception:
            source_meta = {}

    evidence = (source_meta.get("evidence") or "").strip() if isinstance(source_meta, dict) else ""

    tail = []
    if source_url:
        tail.append(f"Source: {source_url}")
    elif source_ref:
        tail.append(f"Source ref: {source_ref}")
    if evidence:
        tail.append(f"Evidence: {evidence}")

    return description + ("\n\n" + "\n".join(tail) if tail else "")


@router.post("/scan-debug")
async def scan_debug(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    if not settings.SLACK_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="SLACK_BOT_TOKEN chua duoc cau hinh")

    result = {"channels": [], "errors": []}
    headers = {"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"}
    oldest = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://slack.com/api/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": 50},
            )
            channels = [channel for channel in response.json().get("channels", []) if not channel.get("is_archived")]

            for channel in channels[:10]:
                channel_id = channel["id"]
                history = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={"channel": channel_id, "oldest": str(oldest), "limit": 50},
                )
                messages = [
                    message.get("text", "")
                    for message in history.json().get("messages", [])
                    if message.get("type") == "message" and message.get("text")
                ]
                content = "\n".join(messages)
                result["channels"].append(
                    {
                        "name": channel.get("name", channel_id),
                        "id": channel_id,
                        "message_count": len(messages),
                        "content_len": len(content),
                        "preview": content[:200] if content else "(empty)",
                        "will_extract": len(content) >= 50,
                    }
                )
    except Exception as exc:
        result["errors"].append({"error": str(exc)})

    return result
