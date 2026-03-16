from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user, require_admin
from apps.api.services.connectors_service import (
    build_connectors_dashboard,
    clear_connector_data,
    clear_all_synced_data,
    create_instance,
    delete_instance,
    discover_connector_scopes,
    list_instances,
    start_all_configured_syncs,
    start_connector_sync,
    test_connector_connection,
    update_connector_config,
    update_instance,
)
from storage.db.db import get_db


router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
async def list_connectors(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return await build_connectors_dashboard(session, can_manage=current_user.is_admin)


@router.get("/stats")
async def get_connector_stats(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # Backward compatible shape for the UI header badges.
    dashboard = await build_connectors_dashboard(session, can_manage=current_user.is_admin)
    stats: dict[str, dict] = {}
    for tab in dashboard.get("tabs") or []:
        for connector in tab.get("instances") or []:
            latest_completed = (connector.get("sync") or {}).get("latest_completed_run") or {}
            stats[str(connector.get("id") or "")] = {
                "documents": (connector.get("data") or {}).get("documents", 0),
                "chunks": (connector.get("data") or {}).get("chunks", 0),
                "last_sync": latest_completed.get("finished_at") or latest_completed.get("last_sync_at") or "No sync yet",
                "status": (connector.get("status") or {}).get("code", ""),
            }
    return {"stats": stats, "summary": dashboard.get("summary") or {}}


@router.post("/sync-all")
async def sync_all_connectors(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await start_all_configured_syncs(session, background_tasks, incremental=True)


class ConnectorConfigRequest(BaseModel):
    enabled: bool | None = None
    auto_sync: bool | None = None
    schedule_hour: int | None = Field(default=None, ge=0, le=23)
    schedule_minute: int | None = Field(default=None, ge=0, le=59)
    selection: dict | None = None


class ConnectorInstanceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str | None = None
    auth_type: str = Field(default="token", max_length=50)  # token|basic
    username: str | None = None
    secret: str | None = None
    extra: dict | None = None


class ConnectorInstanceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = None
    auth_type: str | None = Field(default=None, max_length=50)
    username: str | None = None
    secret: str | None = None
    extra: dict | None = None


@router.get("/{connector_type}/instances")
async def list_connector_instances(
    connector_type: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return {"connector_type": connector_type, "instances": await list_instances(session, connector_type)}


@router.post("/{connector_type}/instances")
async def create_connector_instance(
    connector_type: str,
    req: ConnectorInstanceRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await create_instance(
        session,
        connector_type,
        name=req.name,
        base_url=req.base_url,
        auth_type=req.auth_type,
        username=req.username,
        secret=req.secret,
        extra=req.extra,
    )


@router.put("/{connector_type}/instances/{instance_id}")
async def update_connector_instance(
    connector_type: str,
    instance_id: str,
    req: ConnectorInstanceUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await update_instance(
        session,
        connector_type,
        instance_id,
        name=req.name,
        base_url=req.base_url,
        auth_type=req.auth_type,
        username=req.username,
        secret=req.secret,
        extra=req.extra,
    )


@router.delete("/{connector_type}/instances/{instance_id}")
async def delete_connector_instance(
    connector_type: str,
    instance_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await delete_instance(session, connector_type, instance_id)


@router.post("/{connector_type}/instances/{instance_id}/test")
async def test_connector_instance(
    connector_type: str,
    instance_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await test_connector_connection(session, connector_type, instance_id)


@router.get("/{connector_type}/instances/{instance_id}/discover")
async def discover_connector_instance(
    connector_type: str,
    instance_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await discover_connector_scopes(session, connector_type, instance_id)


@router.put("/{connector_type}/instances/{instance_id}/config")
async def update_connector_instance_config(
    connector_type: str,
    instance_id: str,
    req: ConnectorConfigRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    connector_key = f"{connector_type}:{instance_id}"
    return await update_connector_config(
        session,
        connector_key,
        enabled=req.enabled,
        auto_sync=req.auto_sync,
        schedule_hour=req.schedule_hour,
        schedule_minute=req.schedule_minute,
        selection=req.selection,
    )


@router.post("/{connector_type}/instances/{instance_id}/sync")
async def sync_connector_instance(
    connector_type: str,
    instance_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await start_connector_sync(
        session,
        background_tasks,
        connector_type,
        instance_id,
        incremental=True,
    )


@router.post("/{connector_type}/sync-all")
async def sync_all_for_type(
    connector_type: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await start_all_configured_syncs(session, background_tasks, connector_type=connector_type, incremental=True)


@router.post("/{connector_type}/clear")
async def clear_data_for_type(
    connector_type: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await clear_connector_data(session, connector_type)


@router.post("/clear")
async def clear_connectors_data(
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await clear_all_synced_data(session)
