"""
apps/api/routes/ask.py
POST /ask — ReAct agentic pipeline.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import get_db
from orchestration.agent import Agent
from apps.api.auth.dependencies import get_current_user, CurrentUser
from models.chat import ChatSession, ChatMessage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: str | None = None


class AskResponse(BaseModel):
    answer:          str
    sources:         list[dict]
    rewritten_query: str
    agent_steps:     list[dict] = Field(default_factory=list)
    agent_plan:      list[dict] = Field(default_factory=list)
    used_tools:      list[str]  = Field(default_factory=list)
    session_id:      str | None = None


@router.post("", response_model=AskResponse)
async def ask(
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    POST /ask — Execute ReAct agent pipeline with proper error handling
    
    Returns:
      - 200: AskResponse with answer and sources
      - 400: Invalid question format
      - 503: LLM service unavailable
      - 504: LLM service timeout (too slow)
      - 500: Internal server error
    """
    
    # 1. Validate input
    question = req.question.strip()
    if len(question) < 3 or len(question) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must be 3-1000 characters"
        )
    
    try:
        # 2. Create agent with user context from the start
        agent = Agent(db, current_user.user_id)
        
        # 3. Execute with timeout wrapper (3 minutes)
        result = await asyncio.wait_for(
            agent.ask(question),
            timeout=180
        )

        # Đảm bảo result luôn là dictionary để tránh lỗi AttributeError khi gọi result.get()
        if not result:
            result = {}
        elif not isinstance(result, dict):
            result = {"answer": str(result)}

        # 3.5. Lưu lịch sử chat vào Database
        try:
            session_id = req.session_id
            if not session_id:
                session_id = str(uuid.uuid4())
                title = question[:50] + ("..." if len(question) > 50 else "")
                db.add(ChatSession(id=session_id, user_id=current_user.user_id, title=title))
            else:
                # Cập nhật thời gian updated_at để session trồi lên đầu danh sách Lịch sử
                from sqlalchemy import select
                session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == session_id))).scalar_one_or_none()
                if session_obj:
                    session_obj.updated_at = datetime.now(timezone.utc)
            
            # Lưu câu hỏi của User và câu trả lời của AI
            db.add(ChatMessage(session_id=session_id, role="user", content=question))
            db.add(ChatMessage(session_id=session_id, role="assistant", content=result.get("answer", ""), sources=result.get("sources", [])))
            
            await db.commit()
        except Exception as db_err:
            log.error("ask.save_history_failed", error=str(db_err))
            # Không raise lỗi để người dùng vẫn nhận được câu trả lời dù db lưu xịt
        
        # 4. Validate response has required fields
        return AskResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            rewritten_query=result.get("rewritten_query", question),
            agent_steps=result.get("agent_steps", []),
            agent_plan=result.get("agent_plan", []),
            used_tools=result.get("used_tools", []),
            session_id=session_id,
        )
        
    # 5. Handle specific errors with appropriate HTTP status codes
    except asyncio.TimeoutError:
        log.warning(
            "ask.timeout",
            user_id=current_user.user_id,
            question=question[:100],
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM service is slow. Please try again.",
            headers={"Retry-After": "30"},
        )
    
    except ConnectionError as e:
        log.error(
            "ask.connection_error",
            error=str(e),
            user_id=current_user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is temporarily unavailable. Try again in a few minutes.",
            headers={"Retry-After": "300"},
        )
    
    except ValueError as e:
        # Config error or similar
        log.error("ask.config_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )
    
    except Exception as e:
        log.exception(
            "ask.unexpected_error",
            user_id=current_user.user_id,
            question=question[:100],
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please try again later."
        )
