"""
apps/api/routes/ask.py
POST /ask — ReAct agentic pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import get_db
from orchestration.agent import Agent
from apps.api.auth.dependencies import get_current_user, CurrentUser

router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class AskResponse(BaseModel):
    answer:          str
    sources:         list[dict]
    rewritten_query: str
    agent_steps:     list[dict] = Field(default_factory=list)
    agent_plan:      list[dict] = Field(default_factory=list)
    used_tools:      list[str]  = Field(default_factory=list)


@router.post("", response_model=AskResponse)
async def ask(
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:

        agent = Agent(db)

        result = await agent.ask(
            req.question,
            current_user.user_id
        )

        return AskResponse(**result)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
        )