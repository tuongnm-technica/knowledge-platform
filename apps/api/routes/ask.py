from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from orchestration.agent import Agent

router = APIRouter(prefix="/ask", tags=["ask"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    user_id: str


@router.post("")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    try:
        agent = Agent(db)
        result = await agent.ask(req.question, req.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))