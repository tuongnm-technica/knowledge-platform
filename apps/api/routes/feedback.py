from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from persistence.query_log_repository import QueryLogRepository
from graph.knowledge_graph import KnowledgeGraph

router = APIRouter(prefix="/feedback", tags=["feedback"])

class FeedbackRequest(BaseModel):
    is_positive: bool

@router.post("/{query_id}")
async def submit_feedback(
    query_id: str, 
    req: FeedbackRequest, 
    session: AsyncSession = Depends(get_db)
):
    """
    Điểm trung chuyển Phản hồi người dùng:
    1. Ghi log Feedback vào DB.
    2. Nếu Feedback Positive -> Kích hoạt Reinforcement Engine để tăng Weight đồ thị.
    """
    repo = QueryLogRepository(session)
    feedback_val = 1 if req.is_positive else -1
    
    # Update DB and get metadata
    meta = await repo.submit_feedback(query_id, feedback_val)
    if not meta:
        raise HTTPException(status_code=404, detail="Query log not found")

    # ── SELF-LEARNING ENGINE ──
    if req.is_positive:
        # Lấy danh sách quan hệ đồ thị đã dùng để trả lời câu hỏi này
        edges = meta.get("edges") or []
        if edges:
            graph = KnowledgeGraph(session)
            # Tăng trọng số (Reinforcement) +1 cho mỗi quan hệ thành công
            await graph.reinforce_relations(edges, factor=1)
            
    return {"status": "success", "feedback": feedback_val}
