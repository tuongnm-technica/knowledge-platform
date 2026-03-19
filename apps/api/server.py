from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from contextlib import asynccontextmanager
from pathlib import Path
from storage.db.db import create_tables
from apps.api.routes import search, ask, ingest, health, connectors, auth, users, groups, graph, docs, documents, assets, prompts, tasks, history, memory
from config.settings import settings
from utils.logging import configure_logging
from scheduler.sync_scheduler import start_scheduler, stop_scheduler
from storage.vector.vector_store import get_qdrant
from qdrant_client.models import Distance, VectorParams

import structlog

log     = structlog.get_logger()
WEB_DIR = Path(__file__).parent.parent.parent / "web"

@asynccontextmanager
async def lifespan(app: FastAPI):

    configure_logging(debug=settings.DEBUG)
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

app.include_router(auth.router)
app.include_router(ask.router)
app.include_router(search.router)
app.include_router(ingest.router)
app.include_router(health.router)
app.include_router(connectors.router)
app.include_router(groups.router)
app.include_router(users.router)
app.include_router(graph.router)
app.include_router(docs.router)
app.include_router(documents.router)
app.include_router(assets.router)
app.include_router(prompts.router)
app.include_router(tasks.router)
app.include_router(memory.router)
app.include_router(history.router)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    # Bỏ qua nếu đây là request gọi API nhưng bị sai đường dẫn
    if full_path.startswith("api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not found"}, status_code=404)
        
    index = WEB_DIR / "index.html"
    return FileResponse(index) if index.exists() else {"message": "Place index.html in web/ folder"}
