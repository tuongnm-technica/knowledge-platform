import json
import re
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from storage.db.db import get_db, SDLCJobORM
from permissions.filter import PermissionFilter
from graph.knowledge_graph import KnowledgeGraph
from retrieval.hybrid.hybrid_search import HybridSearch
from persistence.document_repository import DocumentRepository
from ranking.scorer import RankingScorer
from orchestration.agent_workflow import run_sdlc_pipeline, stream_sdlc_pipeline
from arq import create_pool
from arq.connections import RedisSettings
from config.settings import settings
import uuid
from datetime import datetime

log = structlog.get_logger(__name__)

app = FastAPI(title="RAG Microservice", description="Dedicated service for Memory-intensive RAG operations")

class RAGSearchRequest(BaseModel):
    raw: str
    effective: str
    limit: int = 10
    offset: int = 0
    user_id: str
    entities: list[str] = Field(default_factory=list)

class SDLCGenerateRequest(BaseModel):
    request: str
    context: str = ""
    user_id: str

slack_ts_re = re.compile(r"^\[\d{2}:\d{2}\|([0-9]+\.[0-9]+)\]", re.MULTILINE)

def _jsonish(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) if value else {}
        except Exception:
            return {}
    return {}

def _slack_deep_link(channel_id: str, ts: str) -> str:
    ts = str(ts or "").strip()
    if not ts:
        return f"https://slack.com/archives/{channel_id}"
    if "." in ts:
        sec, frac = ts.split(".", 1)
        frac = (frac + "000000")[:6]
        ts_digits = f"{sec}{frac}"
    else:
        ts_digits = "".join([c for c in ts if c.isdigit()])
    return f"https://slack.com/archives/{channel_id}/p{ts_digits}"

def _apply_graph_boost(raw: list[dict], effective_query: str, graph_doc_ids: list[str]) -> list[dict]:
    graph_hits = {str(doc_id) for doc_id in graph_doc_ids}
    for item in raw:
        item["query"] = effective_query
        item["graph_score"] = 1.0 if str(item.get("document_id", "")) in graph_hits else 0.0
    return raw

def _supplement_graph_results(graph_doc_ids: list[str], raw: list[dict], doc_meta: dict[str, dict], effective_query: str) -> list[dict]:
    existing_doc_ids = {str(item.get("document_id", "")) for item in raw}
    supplemented = []
    for doc_id in graph_doc_ids:
        if doc_id in existing_doc_ids:
            continue
        meta = doc_meta.get(doc_id)
        if not meta:
            continue
        supplemented.append(
            {
                "document_id": doc_id,
                "chunk_id": "",
                "content": (meta.get("content") or "")[:500],
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "graph_score": 1.0,
                "query": effective_query,
            }
        )
    return supplemented

@app.post("/search")
async def perform_rag_search(req: RAGSearchRequest, session: AsyncSession = Depends(get_db)):
    log.info("rag_service.search.start", q=req.raw, limit=req.limit, offset=req.offset, user_id=req.user_id)
    
    permissions = PermissionFilter(session)
    graph = KnowledgeGraph(session)
    searcher = HybridSearch(session)
    repo = DocumentRepository(session)
    scorer = RankingScorer()

    try:
        # 1. Permission check
        allowed_ids = await permissions.allowed_docs(req.user_id)
        if allowed_ids is not None and len(allowed_ids) == 0:
            return {"results": []}

        # 2. Graph retrieval
        graph_doc_ids = await graph.find_related_documents(
            req.entities,
            limit=max(req.limit * 5, 20),
        )
        if allowed_ids:
            allowed_set = {str(doc_id) for doc_id in allowed_ids}
            graph_doc_ids = [doc_id for doc_id in graph_doc_ids if str(doc_id) in allowed_set]

        # 3. Hybrid Search
        raw = await searcher.search(
            req.effective,
            top_k=max(req.offset + req.limit + 40, 100),
            allowed_document_ids=allowed_ids,
        )
        
        # 4. Graph Boost & Supplement
        raw = _apply_graph_boost(raw, req.effective, graph_doc_ids)
        
        doc_ids = list({str(item["document_id"]) for item in raw if item.get("document_id")})
        doc_ids.extend([doc_id for doc_id in graph_doc_ids if doc_id not in doc_ids])
        
        # Fetch Metadata
        rows = await repo.get_by_ids(doc_ids)
        doc_meta = {row["id"]: row for row in rows}
        
        raw.extend(_supplement_graph_results(graph_doc_ids, raw, doc_meta, req.effective))

        # 5. Reranking / Scoring
        scored = scorer.score(raw, doc_meta)

        # 6. Deduplicate by document_id
        unique_results: list[dict] = []
        seen_docs = set()
        for item in scored:
            doc_id = str(item.get("document_id", ""))
            if not doc_id or doc_id not in seen_docs:
                unique_results.append(item)
                if doc_id:
                    seen_docs.add(doc_id)

        start = req.offset
        end = start + req.limit
        paginated = unique_results[start:end]
        
        # 7. Format results
        final_results = []
        for item in paginated:
            doc_id = str(item.get("document_id", ""))
            meta = doc_meta.get(doc_id, {})
            url = meta.get("url", "")
            source = meta.get("source", "")
            content = item.get("content", "")

            if source == "slack" and content:
                md = _jsonish(meta.get("metadata"))
                channel_id = str(md.get("channel_id") or "").strip()
                m = slack_ts_re.search(content)
                if channel_id and m:
                    url = _slack_deep_link(channel_id, m.group(1))
                    
            final_results.append({
                "document_id": doc_id,
                "chunk_id": str(item.get("chunk_id", "")),
                "title": meta.get("title", "Unknown"),
                "content": content,
                "url": url,
                "source": source,
                "author": meta.get("author", ""),
                "updated_at": meta.get("updated_at"),
                "score": item.get("final_score", 0.0),
                "score_breakdown": item.get("score_breakdown", {}),
            })

        return {"results": final_results}
        
    except Exception as e:
        log.exception("rag_service.search.failed", error=str(e))
        raise HTTPException(status_code=500, detail="RAG Search execution failed")

@app.post("/generate-sdlc")
async def generate_sdlc_documents(req: SDLCGenerateRequest, session: AsyncSession = Depends(get_db)):
    """
    Endpoint kích hoạt luồng Multi-Agent cho thư viện SDLC
    """
    log.info("rag_service.sdlc.start", user_id=req.user_id, request=req.request[:50])
    try:
        # Chạy toàn bộ pipeline (Search -> BA -> SA -> QA...)
        final_state = await run_sdlc_pipeline(
            user_request=req.request, 
            context=req.context,
            user_id=req.user_id,
            session=session
        )
        
        # Trả về các JSON đã được validate bằng schema
        return {
            "status": "success",
            "data": final_state
        }
    except Exception as e:
        log.exception("rag_service.sdlc.failed", error=str(e))
        raise HTTPException(status_code=500, detail="SDLC Multi-Agent pipeline failed")

@app.post("/stream-sdlc")
async def stream_sdlc_documents(req: SDLCGenerateRequest, session: AsyncSession = Depends(get_db)):
    """
    Endpoint Streaming kích hoạt luồng Multi-Agent cho UI trải nghiệm Real-time
    """
    log.info("rag_service.sdlc_stream.start", user_id=req.user_id)
    
    return StreamingResponse(
        stream_sdlc_pipeline(
            user_request=req.request, 
            context=req.context,
            user_id=req.user_id,
            session=session
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.post("/sdlc/async")
async def generate_sdlc_async(req: SDLCGenerateRequest, session: AsyncSession = Depends(get_db)):
    """
    Khởi tạo một job SDLC chạy ngầm và trả về ID.
    """
    job_id = uuid.uuid4()
    log.info("rag_service.sdlc_async.start", job_id=str(job_id), user_id=req.user_id)
    
    # 1. Lưu job vào DB
    new_job = SDLCJobORM(
        id=job_id,
        user_id=req.user_id,
        request=req.request,
        context=req.context,
        status="processing"
    )
    session.add(new_job)
    await session.commit()
    
    # 2. Enqueue vào Arq
    redis_settings = RedisSettings.from_dsn(getattr(settings, "REDIS_URL", "redis://redis:6379/0"))
    redis_pool = await create_pool(redis_settings)
    await redis_pool.enqueue_job(
        "run_sdlc_generation_job",
        job_id=str(job_id),
        user_request=req.request,
        user_id=req.user_id,
        context=req.context,
        _queue_name="arq:ai"
    )
    
    return {
        "status": "success",
        "job_id": str(job_id)
    }

@app.get("/sdlc/jobs/{job_id}")
async def get_sdlc_job_status(job_id: str, session: AsyncSession = Depends(get_db)):
    """
    Lấy trạng thái và kết quả của một SDLC job.
    """
    from sqlalchemy import select
    result = await session.execute(select(SDLCJobORM).where(SDLCJobORM.id == uuid.UUID(job_id)))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "id": str(job.id),
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "updated_at": job.updated_at
    }