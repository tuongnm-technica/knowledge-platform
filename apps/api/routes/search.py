import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from orchestration.agent import Agent
from query.query_parser import QueryParser
from apps.api.auth.dependencies import get_current_user, CurrentUser
from persistence.document_repository import DocumentRepository

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/search", tags=["search"])
parser = QueryParser()

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)

class SearchResultItem(BaseModel):
    id:              str
    document_id:     str
    chunk_id:        str
    title:           str
    content:         str
    url:             str
    source:          str
    author:          str | None = None
    score:           float
    score_breakdown: dict

class SearchResponse(BaseModel):
    results: list[SearchResultItem]

@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db),
                 current_user: CurrentUser = Depends(get_current_user)):
    try:
        query   = parser.parse(req.query, user_id=current_user.user_id, limit=req.limit, offset=req.offset)
        results = await Agent(db, user_id=current_user.user_id).search(query)
        
        output = []
        for r in results:
            data = {}
            if isinstance(r, dict):
                data = r.copy()
            else:
                data = {
                    "document_id": getattr(r, "document_id", ""),
                    "chunk_id": getattr(r, "chunk_id", ""),
                    "title": getattr(r, "title", "Unknown"),
                    "content": getattr(r, "content", ""),
                    "url": getattr(r, "url", ""),
                    "source": getattr(r, "source", ""),
                    "author": getattr(r, "author", None),
                    "score": getattr(r, "score", 0.0),
                    "score_breakdown": getattr(r, "score_breakdown", {})
                }
            
            # Map id from document_id
            data["id"] = data.get("document_id", "")
            
            output.append(SearchResultItem(**data))
        return {"results": output}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("search.failed", exc_info=e)
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/{document_id}")
async def get_document_details(document_id: str, db: AsyncSession = Depends(get_db),
                               current_user: CurrentUser = Depends(get_current_user)):
    """Lấy chi tiết toàn bộ nội dung của tài liệu (áp dụng filter phân quyền)."""
    repo = DocumentRepository(db)
    rows = await repo.get_by_ids([document_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    
    row = rows[0]
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)