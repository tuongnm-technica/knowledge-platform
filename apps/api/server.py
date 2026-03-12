from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from storage.db.db import create_tables
from apps.api.routes import search, ask, ingest, health, connectors, auth
from apps.api.routes.auth import router as auth_router
from config.settings import settings
from utils.logging import configure_logging
from scheduler.sync_scheduler import start_scheduler, stop_scheduler
import structlog

log     = structlog.get_logger()
WEB_DIR = Path(__file__).parent.parent.parent / "web"

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    log.info("startup.begin", app=settings.APP_NAME)
    await create_tables()
    start_scheduler()
    yield
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

@app.get("/", include_in_schema=False)
async def serve_ui():
    index = WEB_DIR / "index.html"
    return FileResponse(index) if index.exists() else {"message": "Place index.html in web/ folder"}

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")