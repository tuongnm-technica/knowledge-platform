from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from orchestration.agent import Agent
from query.query_parser import QueryParser
from apps.api.auth.dependencies import get_current_user, CurrentUser

router = APIRouter(prefix="/search", tags=["search"])
parser = QueryParser()

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)

class SearchResultItem(BaseModel):
    document_id:     str
    chunk_id:        str
    title:           str
    content:         str
    url:             str
    source:          str
    score:           float
    score_breakdown: dict

@router.post("", response_model=list[SearchResultItem])
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db),
                 current_user: CurrentUser = Depends(get_current_user)):
    try:
        query   = parser.parse(req.query, user_id=current_user.user_id, limit=req.limit, offset=req.offset)
        results = await Agent(db).search(query)
        return [SearchResultItem(document_id=r.document_id, chunk_id=r.chunk_id,
                title=r.title, content=r.content, url=r.url, source=r.source,
                score=r.score, score_breakdown=r.score_breakdown) for r in results]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Search failed")