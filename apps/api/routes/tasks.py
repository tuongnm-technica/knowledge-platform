from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from pydantic import BaseModel

from storage.db.db import get_db
from tasks.repository import TaskDraftRepository
from tasks.scanner import scan_and_create_drafts
from apps.api.auth.dependencies import CurrentUser, require_task_manager

router = APIRouter(prefix="/tasks", tags=["Tasks"])

class StatusUpdateRequest(BaseModel):
    status: str

class TaskUpdatePayload(BaseModel):
    title: str | None = None
    description: str | None = None
    suggested_assignee: str | None = None
    jira_project: str | None = None
    issue_type: str | None = None
    source_meta: dict | None = None
    suggested_fields: dict | None = None

class ScanRequest(BaseModel):
    slack_days: int = 1
    confluence_days: int = 1

@router.get("")
async def get_tasks(
    limit: int = Query(50, ge=1, le=100),
    source: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Lấy danh sách các task (draft) đã được tạo từ AI scanner."""
    repo = TaskDraftRepository(db)
    tasks = await repo.get_all(limit=limit, source=source, status=status)
    return {"tasks": tasks}

@router.get("/count")
async def get_tasks_count(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Đếm số lượng task đang chờ xử lý để hiển thị Notification Badge."""
    repo = TaskDraftRepository(db)
    count = await repo.count_pending()
    return {"total_pending": count}

@router.put("/{task_id}")
async def update_task_details(
    task_id: str,
    req: TaskUpdatePayload,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Cập nhật nội dung chi tiết của task (Title, Description, Assignee...)."""
    repo = TaskDraftRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    from sqlalchemy import text
    updates = []
    params = {"id": task_id}

    # Ánh xạ các trường cần cập nhật theo DB schema
    fields = {
        "title": req.title,
        "description": req.description,
        "suggested_assignee": req.suggested_assignee,
        "jira_project": req.jira_project,
        "issue_type": req.issue_type,
        "source_meta": req.source_meta,
        "suggested_fields": req.suggested_fields,
    }
    
    import json
    for col, val in fields.items():
        if val is not None:
            if col in ("source_meta", "suggested_fields"):
                updates.append(f"{col} = CAST(:{col} AS JSON)")
                params[col] = json.dumps(val)
            else:
                updates.append(f"{col} = :{col}")
                params[col] = val
            
    if updates:
        query = text(f"UPDATE ai_task_drafts SET {', '.join(updates)} WHERE id = :id")
        await db.execute(query, params)
        await db.commit()

    return {"message": "Task updated successfully"}

@router.put("/{task_id}/status")
async def update_task_status(
    task_id: str,
    req: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Cập nhật trạng thái của task (Approve/Reject)."""
    repo = TaskDraftRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    await repo.update_status(task_id, req.status)
    
    # [NEW] Auto-submit to Jira upon approval
    if req.status == "approved":
        from tasks.jira_creator import submit_to_jira
        from config.settings import settings
        
        jira_project = task.get("jira_project") or settings.DEFAULT_JIRA_PROJECT or "ECOS2025"
        issue_type = (task.get("issue_type") or "Task").strip() or "Task"
        epic_key = (task.get("epic_key") or "").strip() or None
        
        desc = task.get("description") or task.get("title")
        if task.get("source_url"):
            desc += f"\n\nSource: {task['source_url']}"
            
        # Pass both source_meta and suggested_fields as extra_fields for Jira
        extra = {}
        if task.get("source_meta"):
            extra.update(task["source_meta"])
        if task.get("suggested_fields"):
            extra.update(task["suggested_fields"])

        jira_result = await submit_to_jira(
            project=jira_project,
            title=task["title"],
            description=desc,
            assignee=task.get("suggested_assignee"),
            priority=task.get("priority") or "Medium",
            labels=task.get("labels") or [],
            components=task.get("components") or [],
            due_date=(task.get("due_date") or None),
            issue_type=issue_type,
            epic_key=epic_key,
            extra_fields=extra,
        )
        if jira_result:
            jira_key = str(jira_result.get("key") or "").strip()
            if jira_key:
                jira_meta = {
                    "jira_assignee_account_id": jira_result.get("assignee_account_id"),
                    "jira_issue_type": jira_result.get("issue_type"),
                }
                await repo.mark_submitted(task_id, jira_key, jira_meta=jira_meta)
                req.status = "submitted"
                
    return {"message": "Status updated successfully", "task_id": task_id, "status": req.status}

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Xóa vĩnh viễn một task bị reject khỏi hệ thống."""
    repo = TaskDraftRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    await repo.delete(task_id)
    return {"message": "Task deleted successfully"}

@router.post("/scan")
async def trigger_task_scan(
    req: ScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_task_manager)
) -> dict[str, Any]:
    """Thủ công kích hoạt quét các nguồn dữ liệu để tìm task mới."""
    stats = await scan_and_create_drafts(
        session=db,
        triggered_by="manual",
        created_by=current_user.user_id,
        slack_days=req.slack_days,
        confluence_days=req.confluence_days
    )
    return {"status": "success", "stats": stats}