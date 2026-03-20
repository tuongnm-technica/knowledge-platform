"""
Thêm vào apps/api/routes/ và mount trong server.py để test search trực tiếp.
GET http://localhost:8000/debug/search?q=đấu+giá+auction&source=all
"""
from fastapi import APIRouter, Query
from retrieval.hybrid.hybrid_search import HybridSearch
from storage.db.db import get_session

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/search")
async def debug_search(
    q: str = Query(..., description="Search query"),
    source: str = Query("all", description="all / slack / confluence / jira / file_server"),
    top_k: int = Query(10),
):
    async with get_session() as session:
        search = HybridSearch(session)
        results = await search.search(q, top_k=top_k * 5)

    if source != "all":
        results = [r for r in results if r.get("source", "") == source]

    return {
        "query": q,
        "source_filter": source,
        "total": len(results),
        "results": [
            {
                "chunk_id":    str(r.get("chunk_id", "")),
                "document_id": str(r.get("document_id", "")),
                "source":      r.get("source", ""),
                "title":       r.get("title", ""),
                "content":     r.get("content", "")[:300],
                "rrf_score":   round(r.get("rrf_score", 0), 4),
                "vector_score":  round(r.get("vector_score", 0), 4),
                "keyword_score": round(r.get("keyword_score", 0), 4),
            }
            for r in results[:top_k]
        ],
    }