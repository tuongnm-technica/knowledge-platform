from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from orchestration.agent import Agent
from query.query_parser import QueryParser

router = APIRouter(prefix="/search", tags=["search"])
parser = QueryParser()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    user_id: str
    limit: int = Field(default=10, ge=1, le=50)


@router.post("")
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    try:
        from models.query import SearchQuery
        query = SearchQuery(raw=req.query, user_id=req.user_id, limit=req.limit)
        agent = Agent(db)
        results = await agent.search(query)
        return [
            {
                "document_id": r.document_id,
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "source": r.source,
                "score": r.score,
                "score_breakdown": r.score_breakdown,
            }
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))