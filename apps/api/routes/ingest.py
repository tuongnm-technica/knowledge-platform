from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from ingestion.pipeline import IngestionPipeline
import structlog

router = APIRouter(prefix="/ingest", tags=["ingest"])
log = structlog.get_logger()


class IngestRequest(BaseModel):
    connector: str  # "slack" | "confluence" | "jira"


@router.post("")
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    connector = _get_connector(req.connector.lower())
    pipeline = IngestionPipeline(db)
    background_tasks.add_task(_run, pipeline, connector)
    return {"status": "started", "connector": req.connector}


async def _run(pipeline, connector):
    try:
        stats = await pipeline.run(connector)
        log.info("ingest.done", **stats)
    except Exception as e:
        log.error("ingest.error", error=str(e))


def _get_connector(name: str):
    try:
        if name == "slack":
            from connectors.slack.slack_connector import SlackConnector
            return SlackConnector()
        if name == "confluence":
            from connectors.confluence.confluence_connector import ConfluenceConnector
            return ConfluenceConnector()
        if name == "jira":
            from connectors.jira.jira_connector import JiraConnector
            return JiraConnector()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    raise HTTPException(status_code=400, detail=f"Unknown connector: {name}")