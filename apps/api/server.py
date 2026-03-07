from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from storage.db.db import create_tables
from apps.api.routes import search, ask, ingest, health
from config.settings import settings
from utils.logging import configure_logging
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    log.info("startup", mode="on-premise",
             llm=settings.OLLAMA_LLM_MODEL,
             embedding=settings.EMBEDDING_MODEL,
             qdrant=f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    await create_tables()
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise AI Knowledge Search — On-Premise",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(search.router)
app.include_router(ask.router)
app.include_router(ingest.router)
app.include_router(health.router)