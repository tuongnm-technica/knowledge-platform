from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
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
    stop_connector_sync,
    test_connector_connection,
    update_connector_config,
    update_instance,
)
from storage.db.db import get_db


router = APIRouter(prefix="/connectors", tags=["connectors"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_run(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": int(row.get("id") or 0),
        "status": str(row.get("status") or ""),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "last_sync_at": _iso(row.get("last_sync_at")),
        "fetched": int(row.get("fetched") or 0),
        "indexed": int(row.get("indexed") or 0),
        "errors": int(row.get("errors") or 0),
    }


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


class SyncStatusRequest(BaseModel):
    connectors: list[str] = Field(default_factory=list, max_length=60)


class SyncTriggerRequest(BaseModel):
    force_full: bool = False


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
    req: SyncTriggerRequest | None = None,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    incremental = True
    if req and req.force_full:
        incremental = False
        
    return await start_connector_sync(
        session,
        background_tasks,
        connector_type,
        instance_id,
        incremental=incremental,
    )

@router.post("/{connector_type}/instances/{instance_id}/stop")
async def stop_connector_instance(
    connector_type: str,
    instance_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await stop_connector_sync(session, connector_type, instance_id)

@router.get("/{connector_type}/instances/{instance_id}/sync/status")
async def connector_sync_status(
    connector_type: str,
    instance_id: str,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    connector_key = f"{connector_type}:{instance_id}"
    row = (
        await session.execute(
            text(
                """
                SELECT id, status, started_at, finished_at, last_sync_at, fetched, indexed, errors
                FROM sync_logs
                WHERE connector = :connector
                ORDER BY COALESCE(started_at, last_sync_at) DESC, id DESC
                LIMIT 1
                """
            ),
            {"connector": connector_key},
        )
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No sync run found for this connector instance.")
    run = _serialize_run(dict(row))
    return {"connector": connector_key, "run": run}


@router.post("/sync/status")
async def connectors_sync_status(
    req: SyncStatusRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    keys = [str(k or "").strip() for k in (req.connectors or []) if str(k or "").strip()]
    seen: set[str] = set()
    connectors: list[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        connectors.append(k)
    if not connectors:
        return {"statuses": {}}
    if len(connectors) > 60:
        raise HTTPException(status_code=400, detail="Too many connectors (max 60).")

    rows = (
        await session.execute(
            text(
                """
                SELECT connector, id, status, started_at, finished_at, last_sync_at, fetched, indexed, errors
                FROM sync_logs
                WHERE connector = ANY(:connectors)
                ORDER BY connector, COALESCE(started_at, last_sync_at) DESC, id DESC
                """
            ),
            {"connectors": connectors},
        )
    ).mappings().all()

    latest: dict[str, dict] = {}
    for r in rows:
        key = str(r.get("connector") or "")
        if not key or key in latest:
            continue
        latest[key] = dict(r)

    statuses: dict[str, dict] = {}
    for key in connectors:
        run = _serialize_run(latest.get(key))
        statuses[key] = {"run": run}
    return {"statuses": statuses}


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
