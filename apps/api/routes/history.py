from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import get_db
from apps.api.auth.dependencies import CurrentUser, get_current_user
from models.chat import ChatSession, ChatMessage

router = APIRouter(prefix="/history", tags=["history"])

@router.get("/sessions")
async def list_sessions(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    stmt = select(ChatSession).where(ChatSession.user_id == current_user.user_id).order_by(desc(ChatSession.updated_at)).limit(limit)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    return {
        "sessions": [
            {"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat() if s.updated_at else None} 
            for s in sessions
        ]
    }

@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Lấy session và check quyền sở hữu
    stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.user_id)
    session = (await db.execute(stmt)).scalars().first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Phiên chat không tồn tại")
        
    # Lấy tin nhắn
    msg_stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    messages = (await db.execute(msg_stmt)).scalars().all()
    
    return {
        "session": {"id": session.id, "title": session.title},
        "messages": [{
            "id": m.id, "role": m.role, "content": m.content, 
            "sources": m.sources, 
            "created_at": m.created_at.isoformat() if m.created_at else None
        } for m in messages]
    }