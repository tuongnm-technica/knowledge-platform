from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from storage.db.db import create_tables
from apps.api.routes import search, ask, ingest, health
from apps.api.routes import connectors
from config.settings import settings
from utils.logging import configure_logging
from scheduler.sync_scheduler import start_scheduler, stop_scheduler
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    log.info("startup.begin",
             app=settings.APP_NAME,
             version=settings.APP_VERSION,
             mode="on-premise",
             llm=f"ollama/{settings.OLLAMA_LLM_MODEL}",
             vector_db=f"qdrant@{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
             embedding=settings.OLLAMA_EMBED_MODEL)

    await create_tables()
    log.info("startup.db_ready")

    # Khởi động auto-sync scheduler
    start_scheduler()
    log.info("startup.scheduler_ready")

    yield

    stop_scheduler()
    log.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
**Enterprise AI Knowledge Search — On-Premise Deployment**

All components run inside the Customer Data Center:
- 🤖 **LLM**: Ollama (deepseek/qwen — no data leaves the network)
- 🔍 **Vector DB**: Qdrant
- 🗄️ **Metadata DB**: PostgreSQL
- 📐 **Embedding**: BGE-M3 via Ollama (local)

## Endpoints
- `POST /search` — Hybrid search (vector + keyword)
- `POST /ask` — AI Q&A with citations
- `POST /ingest` — Trigger connector ingestion (incremental)
- `GET /connectors/stats` — Connector sync stats
- `GET /health` — Check all on-premise components
    """,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(ask.router)
app.include_router(ingest.router)
app.include_router(health.router)
app.include_router(connectors.router)