from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from storage.db.db import create_tables
from apps.api.routes import search, ask, ingest, health, connectors, auth, users, graph, docs, documents, assets, prompts, tasks
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
app.include_router(users.router)
app.include_router(graph.router)
app.include_router(docs.router)
app.include_router(documents.router)
app.include_router(assets.router)
app.include_router(prompts.router)
app.include_router(tasks.router)

@app.get("/", include_in_schema=False)
async def serve_ui():
    index = WEB_DIR / "index.html"
    return FileResponse(index) if index.exists() else {"message": "Place index.html in web/ folder"}

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
