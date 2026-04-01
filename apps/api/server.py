"""
Hệ thống Knowledge Platform - API Server Chính.
File này chịu trách nhiệm:
- Khởi tạo ứng dụng FastAPI.
- Cấu hình Middleware (CORS, Logging).
- Thiết lập lifespan (khởi tạo DB, Vector store, Scheduler).
- Đăng ký (Register) tất cả các tuyến đường (routes) API.
- Cung cấp proxy cho các luồng Multi-Agent nâng cao.
- Serve frontend tĩnh (Static files) và SPA routing.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from contextlib import asynccontextmanager
from pathlib import Path
from storage.db.db import create_tables
from utils.logger_config import configure_logging

from config.settings import settings

# Khởi tạo logging ngay lập tức để tránh lỗi Circular Import khi nạp các routes/tasks
configure_logging(debug=getattr(settings, "DEBUG", False))

from apps.api.routes import search, ask, ingest, health, connectors, auth, users, groups, graph, docs, documents, assets, prompts, tasks, history, memory, workflows, slack, feedback, models, settings as settings_routes, pm_routes
import httpx
from scheduler.sync_scheduler import start_scheduler, stop_scheduler

from storage.vector.vector_store import get_qdrant
from qdrant_client.models import Distance, VectorParams

import structlog

log     = structlog.get_logger()
WEB_DIR = Path(__file__).parent.parent.parent / "web"
if (WEB_DIR / "dist").exists():
    WEB_DIR = WEB_DIR / "dist"

@asynccontextmanager
async def lifespan(app: FastAPI):

    log.info("startup.begin", app=settings.APP_NAME)

    await create_tables()

    # INIT VECTOR DB
    qdrant = get_qdrant()

    collections = [c.name for c in qdrant.get_collections().collections]

    if "semantic_cache" not in collections:

        qdrant.create_collection(
            collection_name="semantic_cache",
            vectors_config=VectorParams(
                size=settings.VECTOR_DIM,  # embedding dimension
                distance=Distance.COSINE,
            ),
        )

        log.info("semantic_cache.collection_created")

    if settings.RUN_WORKER:
        start_scheduler()

    yield

    if settings.RUN_WORKER:
        stop_scheduler()
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION,
              lifespan=lifespan, docs_url="/api/docs", redoc_url="/api/redoc")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(connectors.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(docs.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(slack.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")
app.include_router(pm_routes.router, prefix="/api")

# ==========================================
# SDLC MULTI-AGENT PROXY ROUTES
# ==========================================
RAG_SERVICE_URL = getattr(settings, "RAG_SERVICE_URL", "http://localhost:8001")

@app.post("/api/sdlc/stream")
async def proxy_stream_sdlc(request: Request):
    req_data = await request.json()
    
    async def stream_generator():
        # Timeout lớn (10 phút) vì Local LLM chạy khá lâu cho 3 Agents
        async with httpx.AsyncClient(timeout=600.0) as client: 
            async with client.stream("POST", f"{RAG_SERVICE_URL}/stream-sdlc", json=req_data) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/api/sdlc/generate")
async def proxy_generate_sdlc(request: Request):
    req_data = await request.json()
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(f"{RAG_SERVICE_URL}/generate-sdlc", json=req_data)
        return response.json()

@app.post("/api/sdlc/async")
async def proxy_generate_sdlc_async(request: Request):
    req_data = await request.json()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{RAG_SERVICE_URL}/sdlc/async", json=req_data)
        return response.json()

@app.get("/api/sdlc/jobs/{job_id}")
async def proxy_get_sdlc_job(job_id: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(f"{RAG_SERVICE_URL}/sdlc/jobs/{job_id}")
        return response.json()

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    # Bỏ qua nếu đây là request gọi API nhưng bị sai đường dẫn
    if full_path.startswith("api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not found"}, status_code=404)
        
    # Thử tìm file thực tế trong WEB_DIR (để serve JS, CSS, images, v.v.)
    file_path = WEB_DIR / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
        
    index = WEB_DIR / "index.html"
    return FileResponse(index) if index.exists() else {"message": "Place index.html in web/ folder"}
