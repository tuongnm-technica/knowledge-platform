"""
apps/api/routes/ask.py
POST /ask — ReAct agentic pipeline.
"""

import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from storage.db.db import get_db
from orchestration.agent import Agent
from apps.api.auth.dependencies import get_current_user, CurrentUser
from models.chat import ChatSession, ChatMessage, ChatJob
from utils.queue_client import get_redis_pool
from config.settings import settings


log = structlog.get_logger(__name__)
router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: str | None = None


class AskJobResponse(BaseModel):
    job_id: str
    session_id: str


class AskResponse(BaseModel):
    answer:          str
    sources:         list[dict]
    rewritten_query: str
    agent_steps:     list[dict] = Field(default_factory=list)
    agent_plan:      list[dict] = Field(default_factory=list)
    used_tools:      list[str]  = Field(default_factory=list)
    session_id:      str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    thoughts: list[dict] = Field(default_factory=list)
    result: dict | None = None
    error: str | None = None


@router.post("", response_model=AskJobResponse)
async def ask(
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    POST /ask — Enqueue a ReAct agent job and return job_id immediately.
    """
    question = req.question.strip()
    session_id = req.session_id
    
    # 1. Ensure Chat Session
    if not session_id:
        session_id = str(uuid.uuid4())
        title = question[:50] + ("..." if len(question) > 50 else "")
        db.add(ChatSession(id=session_id, user_id=current_user.user_id, title=title))
    else:
        # Update updated_at
        from sqlalchemy import select
        session_obj = (await db.execute(select(ChatSession).where(ChatSession.id == session_id))).scalar_one_or_none()
        if not session_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        
        session_obj.updated_at = datetime.now(timezone.utc)
    
    # Save user message
    db.add(ChatMessage(session_id=session_id, role="user", content=question))
    
    # 2. Create ChatJob
    job_id = str(uuid.uuid4())
    job = ChatJob(
        id=job_id,
        session_id=session_id,
        user_id=current_user.user_id,
        question=question,
        status="queued"
    )
    db.add(job)
    await db.commit()
    
    # 3. Enqueue to arq
    try:
        redis = await get_redis_pool()
        await redis.enqueue_job(
            "run_agent_job", 
            job_id, 
            current_user.user_id, 
            question, 
            session_id,
            _queue_name=settings.ARQ_AI_QUEUE_NAME
        )
        log.info("ask.job_enqueued", job_id=job_id, user_id=current_user.user_id)
    except Exception as e:
        log.error("ask.enqueue_failed", error=str(e))
        # Optional: update job status to failed in DB if enqueue fails
        raise HTTPException(status_code=500, detail="Failed to enqueue background job")

    return AskJobResponse(job_id=job_id, session_id=session_id)


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    GET /ask/status/{job_id} — Polling endpoint for job status.
    """
    from sqlalchemy import select
    result = await db.execute(select(ChatJob).where(ChatJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        thoughts=job.thoughts or [],
        result=job.result,
        error=job.error
    )
