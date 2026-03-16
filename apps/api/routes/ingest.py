from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, require_admin
from apps.api.services.connectors_service import start_connector_sync
from storage.db.db import get_db


router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    connector: str


@router.post("")
async def ingest(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    payload = await start_connector_sync(
        db,
        background_tasks,
        req.connector.lower(),
        incremental=True,
    )
    payload["triggered_by"] = current_user.email
    return payload
