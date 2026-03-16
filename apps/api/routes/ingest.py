from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from apps.api.auth.dependencies import CurrentUser, require_admin
from apps.api.services.connectors_service import start_connector_sync
from storage.db.db import get_db


router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    connector: str
    instance_id: str | None = None


@router.post("")
async def ingest(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    connector_type = (req.connector or "").strip().lower()
    instance_id = (req.instance_id or "").strip() or None
    if not connector_type:
        return {"status": "skipped", "reason": "Missing connector"}

    if not instance_id:
        # Default: pick the first instance (created_at asc) for this connector type.
        r = await db.execute(
            text(
                """
                SELECT id::text
                FROM connector_instances
                WHERE connector_type = :t
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"t": connector_type},
        )
        instance_id = r.scalar()

    if not instance_id:
        return {"status": "skipped", "reason": "No connector instance found"}

    payload = await start_connector_sync(
        db,
        background_tasks,
        connector_type,
        instance_id,
        incremental=True,
    )
    payload["triggered_by"] = current_user.email
    return payload
