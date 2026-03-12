from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from ingestion.pipeline import IngestionPipeline
from apps.api.auth.dependencies import require_admin, CurrentUser
import structlog

router = APIRouter(prefix="/ingest", tags=["ingest"])
log    = structlog.get_logger()

class IngestRequest(BaseModel):
    connector: str

@router.post("")
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks,
                 db: AsyncSession = Depends(get_db),
                 current_user: CurrentUser = Depends(require_admin)):
    connector = _get_connector(req.connector.lower())
    background_tasks.add_task(_run, IngestionPipeline(db), connector)
    log.info("ingest.triggered", connector=req.connector, by=current_user.email)
    return {"status": "started", "connector": req.connector}

async def _run(pipeline, connector):
    try:
        stats = await pipeline.run(connector)
        log.info("ingest.done", **stats)
    except Exception as e:
        log.error("ingest.error", error=str(e))

def _get_connector(name: str):
    if name == "slack":
        from connectors.slack.slack_connector import SlackConnector
        return SlackConnector()
    if name == "confluence":
        from connectors.confluence.confluence_connector import ConfluenceConnector
        return ConfluenceConnector()
    if name == "jira":
        from connectors.jira.jira_connector import JiraConnector
        return JiraConnector()
    if name == "file_server":
        from connectors.fileserver.smb_connector import SMBConnector
        return SMBConnector()
    raise HTTPException(status_code=400, detail=f"Unknown connector: {name}")