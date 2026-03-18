from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from pydantic import BaseModel

from storage.db.db import get_db
from tasks.repository import TaskDraftRepository

router = APIRouter(prefix="/tasks", tags=["Tasks"])

class StatusUpdateRequest(BaseModel):
    status: str

@router.get("")
async def get_tasks(
    limit: int = Query(50, ge=1, le=100),
    source: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Lấy danh sách các task (draft) đã được tạo từ AI scanner."""
    repo = TaskDraftRepository(db)
    tasks = await repo.get_all(limit=limit, source=source)
    return {"tasks": tasks}

@router.get("/count")
async def get_tasks_count(
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Đếm số lượng task đang chờ xử lý để hiển thị Notification Badge."""
    repo = TaskDraftRepository(db)
    count = await repo.count_pending()
    return {"total_pending": count}

@router.put("/{task_id}/status")
async def update_task_status(
    task_id: str,
    req: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Cập nhật trạng thái của task (Approve/Reject)."""
    repo = TaskDraftRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    await repo.update_status(task_id, req.status)
    return {"message": "Status updated successfully", "task_id": task_id, "status": req.status}

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Xóa vĩnh viễn một task bị reject khỏi hệ thống."""
    repo = TaskDraftRepository(db)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    await repo.delete(task_id)
    return {"message": "Task deleted successfully"}