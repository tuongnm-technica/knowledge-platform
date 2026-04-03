from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any

import structlog
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from utils.queue_client import get_redis_pool
from config.settings import settings
from connectors.confluence.confluence_client import ConfluenceClient
from connectors.confluence.confluence_connector import ConfluenceConnector
from connectors.fileserver.smb_client import SMBClient
from connectors.fileserver.smb_connector import SMBConnector
from connectors.jira.jira_client import JiraClient
from connectors.jira.jira_connector import JiraConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_connector import SlackConnector
from connectors.zoom.zoom_client import ZoomClient
from connectors.zoom.zoom_connector import ZoomConnector
from connectors.google.google_meet_connector import GoogleMeetConnector
from ingestion.pipeline import IngestionPipeline
from storage.db.db import AsyncSessionLocal
from services.rag_service import RAGService


log = structlog.get_logger()


@dataclass(frozen=True)
class ConnectorDefinition:
    key: str
    label: str
    source: str
    description: str
    kind: str
    icon: str
    accent: str
    target_label: str
    scope_label: str
    auth_label: str
    schedule_label: str


CONNECTOR_DEFINITIONS: tuple[ConnectorDefinition, ...] = (
    ConnectorDefinition(
        key="confluence",
        label="Confluence",
        source="confluence",
        description="Pages and spaces with permission-aware ingestion.",
        kind="wiki",
        icon="confluence",
        accent="confluence",
        target_label="Base URL",
        scope_label="Spaces",
        auth_label="API token / Email + token",
        schedule_label="Daily at 02:00",
    ),
    ConnectorDefinition(
        key="jira",
        label="Jira",
        source="jira",
        description="Issues, assignees, project metadata and workflow context.",
        kind="ticketing",
        icon="jira",
        accent="jira",
        target_label="Base URL",
        scope_label="Projects",
        auth_label="API token / Email + token",
        schedule_label="Daily at 02:30",
    ),
    ConnectorDefinition(
        key="slack",
        label="Slack",
        source="slack",
        description="Channels, threads and participant identities from Slack.",
        kind="chat",
        icon="slack",
        accent="slack",
        target_label="Workspace",
        scope_label="Channels",
        auth_label="Bot token",
        schedule_label="Daily at 03:00",
    ),
    ConnectorDefinition(
        key="file_server",
        label="File Server",
        source="file_server",
        description="Shared office documents from SMB network storage.",
        kind="files",
        icon="files",
        accent="files",
        target_label="Share",
        scope_label="Folders",
        auth_label="Username + password",
        schedule_label="Manual only",
    ),
    ConnectorDefinition(
        key="zoom",
        label="Zoom",
        source="zoom",
        description="Meeting recordings and transcripts for indexed knowledge.",
        kind="meetings",
        icon="zoom",
        accent="zoom",
        target_label="Account ID",
        scope_label="Recordings",
        auth_label="Client Secret (+ Client ID in extra)",
        schedule_label="Daily at 04:00",
    ),
    ConnectorDefinition(
        key="google_meet",
        label="Google Meet",
        source="google_meet",
        description="Meeting records and transcripts from Google Drive.",
        kind="meetings",
        icon="google",
        accent="google",
        target_label="Target Folder",
        scope_label="Sub-folders",
        auth_label="Service Account JSON",
        schedule_label="Daily at 04:30",
    ),
)

CONNECTOR_BY_KEY = {definition.key: definition for definition in CONNECTOR_DEFINITIONS}

DEFAULT_SCHEDULES: dict[str, dict[str, Any]] = {
    "confluence": {"auto_sync": True, "hour": 2, "minute": 0, "tz": "Asia/Ho_Chi_Minh"},
    "jira": {"auto_sync": True, "hour": 2, "minute": 30, "tz": "Asia/Ho_Chi_Minh"},
    "slack": {"auto_sync": True, "hour": 3, "minute": 0, "tz": "Asia/Ho_Chi_Minh"},
    "file_server": {"auto_sync": False, "hour": None, "minute": None, "tz": "Asia/Ho_Chi_Minh"},
    "zoom": {"auto_sync": True, "hour": 4, "minute": 0, "tz": "Asia/Ho_Chi_Minh"},
    "google_meet": {"auto_sync": True, "hour": 4, "minute": 30, "tz": "Asia/Ho_Chi_Minh"},
}


def _format_dt(value: Any) -> str | None:
    return value.isoformat() if value else None


def _mask_secret(value: str | None) -> str:
    if not value:
        return "Not configured"
    trimmed = value.strip()
    if len(trimmed) <= 8:
        return "Configured"
    return f"{trimmed[:4]}...{trimmed[-4:]}"


def _get_definition(connector_type: str) -> ConnectorDefinition:
    definition = CONNECTOR_BY_KEY.get(connector_type)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_type}")
    return definition


def _connector_key(connector_type: str, instance_id: str) -> str:
    return f"{connector_type}:{instance_id}"


def _parse_connector_type(connector_key: str) -> str:
    raw = str(connector_key or "").strip()
    return raw.split(":", 1)[0] if ":" in raw else raw


def _csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _schedule_label(config: dict[str, Any] | None, definition: ConnectorDefinition) -> str:
    if not config:
        return definition.schedule_label
    if not config.get("auto_sync"):
        return "Manual only"
    hour = config.get("schedule_hour")
    minute = config.get("schedule_minute")
    if hour is None or minute is None:
        return "Auto sync (time not set)"
    return f"Daily at {int(hour):02d}:{int(minute):02d}"


def _selection_summary(connector_type: str, selection: dict[str, Any]) -> str:
    if not selection:
        return "All accessible"
    if connector_type == "confluence":
        spaces = selection.get("spaces") or []
        return ", ".join(spaces) if spaces else "All spaces"
    if connector_type == "jira":
        projects = selection.get("projects") or []
        return ", ".join(projects) if projects else "All projects"
    if connector_type == "slack":
        channels = selection.get("channels") or []
        return f"{len(channels)} channels selected" if channels else "All channels"
    if connector_type == "file_server":
        folders = selection.get("folders") or []
        return ", ".join(folders) if folders else "All folders"
    if connector_type == "zoom":
        recording_ids = selection.get("recording_ids") or []
        return f"{len(recording_ids)} recordings selected" if recording_ids else "All recordings"
    if connector_type == "google_meet":
        folders = selection.get("folders") or []
        return f"{len(folders)} folders selected" if folders else "Default Recordings folder"
    return "Configured"


def _connector_status(*, configured: bool, running: bool, last_status: str | None, errors: int, documents: int) -> dict[str, str]:
    if not configured:
        return {"code": "not_configured", "tone": "warning", "label": "Not configured", "message": "Missing credentials."}
    if running:
        return {"code": "syncing", "tone": "info", "label": "Syncing", "message": "A sync is in progress."}
    if last_status == "failed":
        return {"code": "attention", "tone": "danger", "label": "Needs attention", "message": "Latest sync failed."}
    if last_status == "partial" and errors > 0:
        return {"code": "attention", "tone": "warning", "label": "Partial sync", "message": "Latest sync had errors."}
    if documents > 0:
        return {"code": "healthy", "tone": "success", "label": "Healthy", "message": "Configured and indexed."}
    return {"code": "ready", "tone": "neutral", "label": "Ready", "message": "Configured and ready to sync."}


async def _ensure_env_instances(session: AsyncSession) -> None:
    async def _has_any(t: str) -> bool:
        r = await session.execute(text("SELECT 1 FROM connector_instances WHERE connector_type = :t LIMIT 1"), {"t": t})
        return r.scalar() is not None

    now = datetime.utcnow()

    if not await _has_any("confluence") and settings.CONFLUENCE_URL and settings.CONFLUENCE_API_TOKEN:
        await session.execute(
            text(
                """
                INSERT INTO connector_instances (id, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at)
                VALUES (:id, 'confluence', 'Default', :base_url, 'token', NULL, :secret, '{}'::json, :created_at, :updated_at)
                """
            ),
            {"id": str(uuid.uuid4()), "base_url": settings.CONFLUENCE_URL, "secret": settings.CONFLUENCE_API_TOKEN, "created_at": now, "updated_at": now},
        )

    if not await _has_any("jira") and settings.JIRA_URL and settings.JIRA_API_TOKEN:
        await session.execute(
            text(
                """
                INSERT INTO connector_instances (id, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at)
                VALUES (:id, 'jira', 'Default', :base_url, 'token', NULL, :secret, '{}'::json, :created_at, :updated_at)
                """
            ),
            {"id": str(uuid.uuid4()), "base_url": settings.JIRA_URL, "secret": settings.JIRA_API_TOKEN, "created_at": now, "updated_at": now},
        )

    if not await _has_any("slack") and settings.SLACK_BOT_TOKEN:
        await session.execute(
            text(
                """
                INSERT INTO connector_instances (id, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at)
                VALUES (:id, 'slack', 'Default', NULL, 'token', NULL, :secret, '{}'::json, :created_at, :updated_at)
                """
            ),
            {"id": str(uuid.uuid4()), "secret": settings.SLACK_BOT_TOKEN, "created_at": now, "updated_at": now},
        )

    if not await _has_any("file_server") and all([settings.SMB_HOST, settings.SMB_SHARE, settings.SMB_USERNAME, settings.SMB_PASSWORD]):
        extra = {"host": settings.SMB_HOST, "share": settings.SMB_SHARE, "base_path": settings.SMB_BASE_PATH}
        await session.execute(
            text(
                """
                INSERT INTO connector_instances (id, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at)
                VALUES (:id, 'file_server', 'Default', :base_url, 'basic', :username, :secret, CAST(:extra AS JSON), :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "base_url": f"\\\\{settings.SMB_HOST}\\{settings.SMB_SHARE}",
                "username": settings.SMB_USERNAME,
                "secret": settings.SMB_PASSWORD,
                "extra": json.dumps(extra),
                "created_at": now,
                "updated_at": now,
            },
        )

    await session.commit()


async def list_instances(session: AsyncSession, connector_type: str) -> list[dict[str, Any]]:
    _get_definition(connector_type)
    await _ensure_env_instances(session)

    result = await session.execute(
        text(
            """
            SELECT id::text, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at
            FROM connector_instances
            WHERE connector_type = :t
            ORDER BY created_at ASC, name ASC
            """
        ),
        {"t": connector_type},
    )
    rows = [dict(r) for r in result.mappings().all()]
    for r in rows:
        raw_secret = r.get("secret")
        if isinstance(r.get("extra"), str):
            try:
                r["extra"] = json.loads(r["extra"]) if r["extra"] else {}
            except Exception:
                r["extra"] = {}
        r["key"] = _connector_key(connector_type, r["id"])
        r["secret_preview"] = _mask_secret(raw_secret)
        r["has_secret"] = bool(str(raw_secret or "").strip())
        # Never return raw secrets to the UI.
        r.pop("secret", None)
        r["auth_type"] = (r.get("auth_type") or "token").strip().lower()
        r["username"] = r.get("username") or ""
        r["base_url"] = r.get("base_url") or ""
    return rows


async def create_instance(
    session: AsyncSession,
    connector_type: str,
    *,
    name: str,
    base_url: str | None = None,
    auth_type: str = "token",
    username: str | None = None,
    secret: str | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    _get_definition(connector_type)
    instance_id = str(uuid.uuid4())
    now = datetime.utcnow()
    await session.execute(
        text(
            """
            INSERT INTO connector_instances (id, connector_type, name, base_url, auth_type, username, secret, extra, created_at, updated_at)
            VALUES (:id, :t, :name, :base_url, :auth_type, :username, :secret, CAST(:extra AS JSON), :created_at, :updated_at)
            """
        ),
        {
            "id": instance_id,
            "t": connector_type,
            "name": (name or "").strip() or "Untitled",
            "base_url": (base_url or "").strip() or None,
            "auth_type": (auth_type or "token").strip().lower(),
            "username": (username or "").strip() or None,
            "secret": (secret or "").strip() or None,
            "extra": json.dumps(extra or {}),
            "created_at": now,
            "updated_at": now,
        },
    )
    await session.commit()
    return {"id": instance_id, "key": _connector_key(connector_type, instance_id)}


async def update_instance(
    session: AsyncSession,
    connector_type: str,
    instance_id: str,
    *,
    name: str | None = None,
    base_url: str | None = None,
    auth_type: str | None = None,
    username: str | None = None,
    secret: str | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    _get_definition(connector_type)

    updates: list[str] = ["updated_at = NOW()"]
    params: dict[str, Any] = {"id": instance_id, "t": connector_type}

    if name is not None:
        updates.append("name = :name")
        params["name"] = (name or "").strip() or "Untitled"
    if base_url is not None:
        updates.append("base_url = :base_url")
        params["base_url"] = (base_url or "").strip() or None
    if auth_type is not None:
        updates.append("auth_type = :auth_type")
        params["auth_type"] = (auth_type or "token").strip().lower()
    if username is not None:
        updates.append("username = :username")
        params["username"] = (username or "").strip() or None
    if secret is not None:
        updates.append("secret = :secret")
        params["secret"] = (secret or "").strip() or None
    if extra is not None:
        updates.append("extra = CAST(:extra AS JSON)")
        params["extra"] = json.dumps(extra or {})

    result = await session.execute(
        text(f"UPDATE connector_instances SET {', '.join(updates)} WHERE id::text = :id AND connector_type = :t"),
        params,
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Connector instance not found")
    await session.commit()
    return {"status": "updated", "id": instance_id, "key": _connector_key(connector_type, instance_id)}


async def delete_instance(session: AsyncSession, connector_type: str, instance_id: str) -> dict[str, Any]:
    _get_definition(connector_type)
    key = _connector_key(connector_type, instance_id)
    await session.execute(text("DELETE FROM connector_configs WHERE connector = :c"), {"c": key})
    await session.execute(
        text("DELETE FROM connector_instances WHERE id::text = :id AND connector_type = :t"),
        {"id": instance_id, "t": connector_type},
    )
    await session.commit()
    return {"status": "deleted", "id": instance_id}


async def _ensure_connector_config(session: AsyncSession, connector_key: str) -> dict[str, Any]:
    connector_type = _parse_connector_type(connector_key)
    defaults = DEFAULT_SCHEDULES.get(connector_type, {})

    selection: dict[str, Any] = {}
    if connector_type == "confluence":
        selection = {"spaces": _csv_values(settings.CONFLUENCE_SPACE_KEYS)}
    elif connector_type == "jira":
        selection = {"projects": _csv_values(settings.JIRA_PROJECT_KEYS)}
    elif connector_type == "slack":
        selection = {"channels": []}
    elif connector_type == "file_server":
        selection = {"folders": []}
    elif connector_type == "zoom":
        selection = {"recording_ids": []}

    await session.execute(
        text(
            """
            INSERT INTO connector_configs (
                connector, enabled, auto_sync, schedule_hour, schedule_minute, schedule_tz, selection
            )
            VALUES (
                :connector, TRUE, :auto_sync, :schedule_hour, :schedule_minute, :schedule_tz, CAST(:selection AS JSON)
            )
            ON CONFLICT (connector) DO NOTHING
            """
        ),
        {
            "connector": connector_key,
            "auto_sync": bool(defaults.get("auto_sync", False)),
            "schedule_hour": defaults.get("hour"),
            "schedule_minute": defaults.get("minute"),
            "schedule_tz": defaults.get("tz") or "Asia/Ho_Chi_Minh",
            "selection": json.dumps(selection),
        },
    )
    await session.commit()

    result = await session.execute(
        text(
            """
            SELECT connector, enabled, auto_sync, schedule_hour, schedule_minute, schedule_tz, selection, updated_at
            FROM connector_configs
            WHERE connector = :connector
            """
        ),
        {"connector": connector_key},
    )
    row = result.mappings().first()
    config = dict(row) if row else {}

    selection_value = config.get("selection") or {}
    if isinstance(selection_value, str):
        try:
            selection_value = json.loads(selection_value) if selection_value else {}
        except Exception:
            selection_value = {}
    config["selection"] = selection_value if isinstance(selection_value, dict) else {}
    return config


async def update_connector_config(
    session: AsyncSession,
    connector_key: str,
    *,
    enabled: bool | None = None,
    auto_sync: bool | None = None,
    schedule_hour: int | None = None,
    schedule_minute: int | None = None,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    await _ensure_connector_config(session, connector_key)

    updates: list[str] = ["updated_at = NOW()"]
    params: dict[str, Any] = {"connector": connector_key}

    if enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = bool(enabled)
    if auto_sync is not None:
        updates.append("auto_sync = :auto_sync")
        params["auto_sync"] = bool(auto_sync)
    if schedule_hour is not None:
        updates.append("schedule_hour = :schedule_hour")
        params["schedule_hour"] = int(schedule_hour)
    if schedule_minute is not None:
        updates.append("schedule_minute = :schedule_minute")
        params["schedule_minute"] = int(schedule_minute)
    if selection is not None:
        updates.append("selection = CAST(:selection AS JSON)")
        params["selection"] = json.dumps(selection)

    await session.execute(text(f"UPDATE connector_configs SET {', '.join(updates)} WHERE connector = :connector"), params)
    await session.commit()

    try:
        from scheduler.sync_scheduler import trigger_scheduler_refresh

        trigger_scheduler_refresh()
    except Exception:
        pass

    return await _ensure_connector_config(session, connector_key)


async def _latest_sync(session: AsyncSession, connector_key: str, *, include_running: bool) -> dict[str, Any] | None:
    extra = "" if include_running else "AND status != 'running'"
    result = await session.execute(
        text(
            f"""
            SELECT id, status, started_at, finished_at, last_sync_at, fetched, indexed, errors
            FROM sync_logs
            WHERE connector = :connector
            {extra}
            ORDER BY COALESCE(started_at, last_sync_at) DESC, id DESC
            LIMIT 1
            """
        ),
        {"connector": connector_key},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _recent_sync_runs(session: AsyncSession, connector_key: str, *, limit: int = 6) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT id, status, started_at, finished_at, last_sync_at, fetched, indexed, errors
            FROM sync_logs
            WHERE connector = :connector
            ORDER BY COALESCE(started_at, last_sync_at) DESC, id DESC
            LIMIT :limit
            """
        ),
        {"connector": connector_key, "limit": limit},
    )
    return [dict(row) for row in result.mappings().all()]


def _serialize_run(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "started_at": _format_dt(row["started_at"]),
        "finished_at": _format_dt(row["finished_at"]),
        "last_sync_at": _format_dt(row["last_sync_at"]),
        "fetched": int(row["fetched"] or 0),
        "indexed": int(row["indexed"] or 0),
        "errors": int(row["errors"] or 0),
    }


async def _count_documents(session: AsyncSession, connector_key: str, connector_type: str) -> int:
    result = await session.execute(
        text("SELECT COUNT(*) FROM documents WHERE metadata->>'connector_key' = :k"),
        {"k": connector_key},
    )
    v = int(result.scalar() or 0)
    if v:
        return v
    if connector_key == connector_type:
        r2 = await session.execute(text("SELECT COUNT(*) FROM documents WHERE source = :s"), {"s": connector_type})
        return int(r2.scalar() or 0)
    return 0


async def _count_chunks(session: AsyncSession, connector_key: str, connector_type: str) -> int:
    result = await session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.metadata->>'connector_key' = :k
            """
        ),
        {"k": connector_key},
    )
    v = int(result.scalar() or 0)
    if v:
        return v
    if connector_key == connector_type:
        r2 = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.source = :s
                """
            ),
            {"s": connector_type},
        )
        return int(r2.scalar() or 0)
    return 0


def _instance_missing_fields(connector_type: str, inst: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    auth_type = str(inst.get("auth_type") or "token").strip().lower()
    base_url = str(inst.get("base_url") or "").strip()
    username = str(inst.get("username") or "").strip()
    # list_instances() intentionally strips raw secrets from API responses.
    # For dashboard/config validation we only need to know whether a secret exists.
    if "secret" in inst:
        secret = str(inst.get("secret") or "").strip()
    else:
        secret = "configured" if bool(inst.get("has_secret")) else ""
    extra = inst.get("extra") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra else {}
        except Exception:
            extra = {}

    if connector_type in {"confluence", "jira"}:
        if not base_url:
            missing.append("base_url")
        if auth_type == "basic":
            if not username:
                missing.append("username")
            if not secret:
                missing.append("api_token")
        else:
            if not secret:
                missing.append("api_token")
        return missing

    if connector_type == "slack":
        if not secret:
            missing.append("bot_token")
        return missing

    if connector_type == "file_server":
        if not username:
            missing.append("username")
        if not secret:
            missing.append("password")
        if not str(extra.get("host") or settings.SMB_HOST or "").strip():
            missing.append("host")
        if not str(extra.get("share") or settings.SMB_SHARE or "").strip():
            missing.append("share")
        return missing

    if connector_type == "zoom":
        if not username: # We use username field for account_id
            missing.append("account_id")
        if not secret: # We use secret field for client_secret
            missing.append("client_secret")
        if not str(extra.get("client_id") or "").strip():
            missing.append("client_id")
        return missing
    
    if connector_type == "google_meet":
        if not secret: # Service account JSON stored in secret
            missing.append("service_account_json")
        return missing

    return ["unknown_connector"]


async def _fetch_instance(session: AsyncSession, connector_type: str, instance_id: str) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            SELECT id::text, connector_type, name, base_url, auth_type, username, secret, extra
            FROM connector_instances
            WHERE connector_type = :t AND id::text = :id
            """
        ),
        {"t": connector_type, "id": instance_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Connector instance not found")
    inst = dict(row)
    if isinstance(inst.get("extra"), str):
        try:
            inst["extra"] = json.loads(inst["extra"]) if inst["extra"] else {}
        except Exception:
            inst["extra"] = {}
    return inst


def _build_connector(connector_type: str, inst: dict[str, Any], selection: dict[str, Any] | None) -> Any:
    selection = selection or {}
    auth_type = str(inst.get("auth_type") or "token").strip().lower()
    username = str(inst.get("username") or "").strip() or None
    secret = str(inst.get("secret") or "").strip() or None
    base_url = str(inst.get("base_url") or "").strip() or None
    extra = inst.get("extra") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra else {}
        except Exception:
            extra = {}

    if connector_type == "confluence":
        spaces = set((selection or {}).get("spaces") or []) or None
        return ConfluenceConnector(
            space_keys=spaces,
            base_url=base_url,
            username=username if auth_type == "basic" else None,
            api_token=secret,
        )
    if connector_type == "jira":
        projects = set((selection or {}).get("projects") or []) or None
        return JiraConnector(
            project_keys=projects,
            base_url=base_url,
            username=username if auth_type == "basic" else None,
            api_token=secret,
        )
    if connector_type == "slack":
        channels = set((selection or {}).get("channels") or []) or None
        return SlackConnector(channel_ids=channels, bot_token=secret)
    if connector_type == "file_server":
        folders = set((selection or {}).get("folders") or []) or None
        host = str(extra.get("host") or settings.SMB_HOST or "").strip()
        share = str(extra.get("share") or settings.SMB_SHARE or "").strip()
        base_path = str(extra.get("base_path") or settings.SMB_BASE_PATH or "").strip() or "\\"
        return SMBConnector(
            folders=folders,
            host=host,
            share=share,
            username=username or settings.SMB_USERNAME,
            password=secret or settings.SMB_PASSWORD,
            base_path=base_path,
        )
    if connector_type == "zoom":
        recording_ids = set((selection or {}).get("recording_ids") or []) or None
        return ZoomConnector(
            account_id=username or settings.ZOOM_ACCOUNT_ID,
            client_id=str(extra.get("client_id") or settings.ZOOM_CLIENT_ID or "").strip(),
            client_secret=secret or settings.ZOOM_CLIENT_SECRET,
            recording_ids=recording_ids
        )
    if connector_type == "google_meet":
        folders = set((selection or {}).get("folders") or []) or None
        return GoogleMeetConnector(
            service_account_json=secret or settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON,
            folder_name=str(extra.get("folder_name") or "").strip() or "Meeting Recordings"
        )
    raise HTTPException(status_code=400, detail=f"Unsupported connector type: {connector_type}")


async def build_connector_for_instance(
    session: AsyncSession,
    connector_type: str,
    instance_id: str,
    selection: dict[str, Any] | None,
) -> Any:
    """
    Public helper for scheduler: build a connector from a DB instance + selection.
    """
    inst = await _fetch_instance(session, connector_type, instance_id)
    return _build_connector(connector_type, inst, selection)


async def build_connectors_dashboard(session: AsyncSession, *, can_manage: bool) -> dict[str, Any]:
    await _ensure_env_instances(session)

    tabs: list[dict[str, Any]] = []
    summary = {"total": 0, "configured": 0, "healthy": 0, "attention": 0, "syncing": 0, "documents": 0, "chunks": 0}

    for definition in CONNECTOR_DEFINITIONS:
        instances = await list_instances(session, definition.key)
        cards: list[dict[str, Any]] = []

        for inst in instances:
            connector_key = inst["key"]
            config_state = await _ensure_connector_config(session, connector_key)
            missing = _instance_missing_fields(definition.key, inst)
            configured = len(missing) == 0

            documents = await _count_documents(session, connector_key, definition.source)
            chunks = await _count_chunks(session, connector_key, definition.source)
            latest_run = await _latest_sync(session, connector_key, include_running=True)
            latest_completed = await _latest_sync(session, connector_key, include_running=False)
            history = await _recent_sync_runs(session, connector_key)

            running = bool(latest_run and latest_run["status"] == "running" and latest_run["finished_at"] is None)
            last_status = latest_run["status"] if latest_run else None
            latest_errors = int((latest_run or {}).get("errors") or 0)
            status = _connector_status(
                configured=configured,
                running=running,
                last_status=last_status,
                errors=latest_errors,
                documents=documents,
            )

            cards.append(
                {
                    "id": connector_key,
                    "connector_type": definition.key,
                    "instance_id": inst["id"],
                    "instance_name": inst.get("name") or "Untitled",
                    "name": f"{definition.label}: {inst.get('name') or inst.get('id')}",
                    "description": definition.description,
                    "kind": definition.kind,
                    "icon": definition.icon,
                    "accent": definition.accent,
                    "configured": configured,
                    "base_url": inst.get("base_url") or "",
                    "scope_label": definition.scope_label,
                    "scope_value": _selection_summary(definition.key, config_state.get("selection") or {}),
                    "missing_settings": missing,
                    "status": status,
                    "state": {
                        "enabled": bool(config_state.get("enabled", True)),
                        "auto_sync": bool(config_state.get("auto_sync", False)),
                        "schedule_hour": config_state.get("schedule_hour"),
                        "schedule_minute": config_state.get("schedule_minute"),
                        "schedule_tz": config_state.get("schedule_tz") or "Asia/Ho_Chi_Minh",
                        "selection": config_state.get("selection") or {},
                    },
                    "config": {
                        "target_label": definition.target_label,
                        "target_value": inst.get("base_url") or "",
                        "scope_label": definition.scope_label,
                        "scope_value": _selection_summary(definition.key, config_state.get("selection") or {}),
                        "auth_label": definition.auth_label,
                        "auth_value": inst.get("secret_preview") or "Not configured",
                        "username": inst.get("username") or "",
                        "auth_type": inst.get("auth_type") or "token",
                        "extra": inst.get("extra") or {},
                    },
                    "sync": {
                        "schedule_label": _schedule_label(config_state, definition),
                        "running": running,
                        "latest_run": _serialize_run(latest_run),
                        "latest_completed_run": _serialize_run(latest_completed),
                        "history": [_serialize_run(run) for run in history],
                    },
                    "data": {"documents": documents, "chunks": chunks},
                    "actions": {
                        "can_manage": can_manage,
                        "can_test": configured and can_manage,
                        "can_sync": bool(config_state.get("enabled", True)) and configured and can_manage and not running,
                        "can_discover": configured and can_manage,
                        "can_clear": can_manage,
                    },
                }
            )

            summary["total"] += 1
            summary["documents"] += int(documents or 0)
            summary["chunks"] += int(chunks or 0)
            if configured:
                summary["configured"] += 1
            if status["code"] == "healthy":
                summary["healthy"] += 1
            if status["code"] in {"attention", "not_configured"}:
                summary["attention"] += 1
            if running:
                summary["syncing"] += 1

        tabs.append({"type": definition.key, "label": definition.label, "instances": cards})

    return {"summary": summary, "tabs": tabs}


async def start_connector_sync(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    connector_type: str,
    instance_id: str,
    *,
    incremental: bool = True,
    summarize: bool | None = None,
    relations: bool | None = None,
    vision: bool | None = None,
) -> dict[str, Any]:
    inst = await _fetch_instance(session, connector_type, instance_id)
    connector_key = _connector_key(connector_type, instance_id)
    cfg = await _ensure_connector_config(session, connector_key)

    if not bool(cfg.get("enabled", True)):
        return {"status": "skipped", "reason": "Disabled"}
    missing = _instance_missing_fields(connector_type, inst)
    if missing:
        return {"status": "skipped", "reason": f"Missing: {', '.join(missing)}"}

    latest_run = await _latest_sync(session, connector_key, include_running=True)
    if latest_run and latest_run.get("status") == "running" and latest_run.get("finished_at") is None:
        return {"status": "skipped", "reason": "Already syncing"}

    selection = cfg.get("selection") or {}
    connector = _build_connector(connector_type, inst, selection)

    # 1. Bơm log 'running' vào DB để UI hiển thị thanh tiến độ ngay lập tức
    now = datetime.utcnow()
    await session.execute(
        text(
            """
            INSERT INTO sync_logs (connector, status, started_at)
            VALUES (:connector, 'running', :now)
            """
        ),
        {"connector": connector_key, "now": now}
    )
    await session.commit()

    # 2. Đẩy job vào queue (chỉ định đúng queue ingestion) hoặc chạy nền nếu lỗi
    try:
        redis = await get_redis_pool()
        queue_name = getattr(settings, "ARQ_INGESTION_QUEUE_NAME", "ingestion")
        await redis.enqueue_job(
            "sync_connector_job", 
            connector_type, 
            instance_id, 
            incremental, 
            summarize, 
            relations,
            vision,
            _queue_name=queue_name
        )
        log.info("connectors.sync.queued", key=connector_key, queue=queue_name)
    except Exception as e:
        log.error("connectors.sync.redis_failed_fallback", error=str(e))
        background_tasks.add_task(_run_sync_task, connector_type, instance_id, incremental, summarize, relations, vision)

    return {"status": "started", "connector": connector_key, "incremental": incremental}

async def stop_connector_sync(
    session: AsyncSession,
    connector_type: str,
    instance_id: str,
) -> dict[str, Any]:
    connector_key = _connector_key(connector_type, instance_id)
    result = await session.execute(
        text(
            """
            UPDATE sync_logs
            SET status = 'cancelled', last_sync_at = NOW()
            WHERE connector = :connector AND status = 'running'
            RETURNING id
            """
        ),
        {"connector": connector_key}
    )
    await session.commit()
    
    if result.rowcount > 0:
        return {"status": "stopping", "connector": connector_key, "message": "Signal sent to stop sync."}
    return {"status": "not_running", "connector": connector_key, "message": "No running sync found to stop."}
    return {"status": "started", "connector": connector_key, "incremental": incremental}


async def _run_sync_task(
    connector_type: str, 
    instance_id: str, 
    incremental: bool,
    summarize: bool | None = None,
    relations: bool | None = None,
    vision: bool | None = None
) -> None:
    connector_key = _connector_key(connector_type, instance_id)
    try:
        async with AsyncSessionLocal() as session:
            inst = await _fetch_instance(session, connector_type, instance_id)
            cfg = await _ensure_connector_config(session, connector_key)
            selection = cfg.get("selection") or {}
            connector = _build_connector(connector_type, inst, selection)
            pipeline = IngestionPipeline(session)
            
            start = perf_counter()
            stats = await pipeline.run(
                connector, 
                incremental=incremental, 
                connector_key=connector_key,
                summarize=summarize,
                relations=relations,
                vision=vision
            )
            log.info("connectors.sync.done", key=connector_key, elapsed=round(perf_counter() - start, 2), **stats)
            
            # Post-sync: Trigger PM Metrics Aggregation if Jira
            if connector_type == "jira":
                try:
                    from utils.queue_client import get_redis_pool
                    redis = await get_redis_pool()
                    projects = selection.get("projects") or []
                    if not projects:
                        # Fallback: get distinct projects from DB for this connector
                        res = await session.execute(text("SELECT DISTINCT metadata->>'project_key' FROM documents WHERE source = 'jira'"))
                        projects = [row[0] for row in res.fetchall() if row[0]]
                    
                    for p in projects:
                        await redis.enqueue_job("aggregate_pm_metrics", p, _queue_name="arq:ai")
                        await redis.enqueue_job("generate_pm_digest", [p], _queue_name="arq:ai")
                        log.info("pm_metrics_and_digest.trigger.queued", project=p)
                except Exception as e:
                    log.error("pm_metrics.trigger.failed", error=str(e))
    except Exception as e:
        log.exception("connectors.sync.failed_bg_task", key=connector_key, error=str(e))
        # Đảm bảo tắt thanh tiến độ nếu pipeline bị crash ngầm
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    UPDATE sync_logs 
                    SET status = 'failed', finished_at = :now, errors = errors + 1
                    WHERE connector = :c AND status = 'running'
                """),
                {"c": connector_key, "now": datetime.utcnow()}
            )
            await session.commit()


async def start_all_configured_syncs(
    session: AsyncSession,
    background_tasks: BackgroundTasks,
    *,
    connector_type: str | None = None,
    incremental: bool = True,
) -> dict[str, Any]:
    await _ensure_env_instances(session)

    started: list[str] = []
    skipped: list[dict[str, str]] = []
    types = [connector_type] if connector_type else [d.key for d in CONNECTOR_DEFINITIONS]

    for t in types:
        instances = await list_instances(session, t)
        for inst in instances:
            connector_key = inst["key"]
            cfg = await _ensure_connector_config(session, connector_key)
            if not bool(cfg.get("enabled", True)):
                skipped.append({"connector": connector_key, "reason": "Disabled"})
                continue
            if _instance_missing_fields(t, inst):
                skipped.append({"connector": connector_key, "reason": "Not configured"})
                continue
            latest_run = await _latest_sync(session, connector_key, include_running=True)
            if latest_run and latest_run.get("status") == "running" and latest_run.get("finished_at") is None:
                skipped.append({"connector": connector_key, "reason": "Already syncing"})
                continue
                
            now = datetime.utcnow()
            await session.execute(
                text(
                    """
                    INSERT INTO sync_logs (connector, status, started_at)
                    VALUES (:connector, 'running', :now)
                    """
                ),
                {"connector": connector_key, "now": now}
            )
            await session.commit()

            try:
                redis = await get_redis_pool()
                queue_name = getattr(settings, "ARQ_INGESTION_QUEUE_NAME", "ingestion")
                await redis.enqueue_job("sync_connector_job", t, inst["id"], incremental, _queue_name=queue_name)
                log.info("connectors.sync.all_queued", key=connector_key, queue=queue_name)
            except Exception as e:
                log.error("connectors.sync.redis_failed_fallback", error=str(e), advice="Check if Redis is running and REDIS_URL is correct.")
                background_tasks.add_task(_run_sync_task, t, inst["id"], incremental)
                
            started.append(connector_key)

    return {"status": "started" if started else "skipped", "started": started, "skipped": skipped, "incremental": incremental}


async def test_connector_connection(session: AsyncSession, connector_type: str, instance_id: str) -> dict[str, Any]:
    inst = await _fetch_instance(session, connector_type, instance_id)
    missing = _instance_missing_fields(connector_type, inst)
    if missing:
        return {"status": "error", "message": f"Missing: {', '.join(missing)}"}

    try:
        if connector_type == "confluence":
            client = ConfluenceClient(
                base_url=inst.get("base_url"),
                api_token=inst.get("secret"),
                username=inst.get("username"),
                auth_type=inst.get("auth_type"),
            )
            ok = await asyncio.to_thread(client.test_connection)
            return {"status": "ok" if ok else "error"}
        if connector_type == "jira":
            client = JiraClient(
                base_url=inst.get("base_url"),
                api_token=inst.get("secret"),
                username=inst.get("username"),
                auth_type=inst.get("auth_type"),
            )
            ok = await asyncio.to_thread(client.test_connection)
            return {"status": "ok" if ok else "error"}
        if connector_type == "slack":
            client = SlackClient(bot_token=inst.get("secret"))
            ok = await client.test_connection()
            return {"status": "ok" if ok else "error"}
        if connector_type == "file_server":
            extra = inst.get("extra") or {}
            host = str(extra.get("host") or settings.SMB_HOST or "").strip()
            share = str(extra.get("share") or settings.SMB_SHARE or "").strip()
            client = SMBClient(
                host=host,
                share=share,
                username=inst.get("username") or settings.SMB_USERNAME,
                password=inst.get("secret") or settings.SMB_PASSWORD,
            )
            ok = await asyncio.to_thread(client.test_connection)
            return {"status": "ok" if ok else "error"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    return {"status": "error", "message": "Unsupported connector"}


async def discover_connector_scopes(session: AsyncSession, connector_type: str, instance_id: str) -> dict[str, Any]:
    inst = await _fetch_instance(session, connector_type, instance_id)
    missing = _instance_missing_fields(connector_type, inst)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing: {', '.join(missing)}")

    if connector_type == "confluence":
        client = ConfluenceClient(
            base_url=inst.get("base_url"),
            api_token=inst.get("secret"),
            username=inst.get("username"),
            auth_type=inst.get("auth_type"),
        )
        spaces = await asyncio.to_thread(client.get_spaces)
        items = [{"key": s.get("key", ""), "name": s.get("name", s.get("key", ""))} for s in spaces if s.get("key")]
        return {"connector": connector_type, "items": items}

    if connector_type == "jira":
        client = JiraClient(
            base_url=inst.get("base_url"),
            api_token=inst.get("secret"),
            username=inst.get("username"),
            auth_type=inst.get("auth_type"),
        )
        projects = await asyncio.to_thread(client.get_projects, filter_allowed=False)
        items = [{"key": p.get("key", ""), "name": p.get("name", p.get("key", ""))} for p in projects if p.get("key")]
        return {"connector": connector_type, "items": items}

    if connector_type == "slack":
        client = SlackClient(bot_token=inst.get("secret"))
        channels = await client.get_channels()
        items = [
            {"id": c.get("id", ""), "name": c.get("name", c.get("id", "")), "is_private": bool(c.get("is_private"))}
            for c in channels
            if c.get("id")
        ]
        return {"connector": connector_type, "items": items}

    if connector_type == "file_server":
        extra = inst.get("extra") or {}
        host = str(extra.get("host") or settings.SMB_HOST or "").strip()
        share = str(extra.get("share") or settings.SMB_SHARE or "").strip()
        base_path = str(extra.get("base_path") or settings.SMB_BASE_PATH or "").strip() or "\\"
        client = SMBClient(
            host=host,
            share=share,
            username=inst.get("username") or settings.SMB_USERNAME,
            password=inst.get("secret") or settings.SMB_PASSWORD,
        )
        folders = await asyncio.to_thread(client.list_top_folders, base_path)
        items = [{"name": f} for f in folders]
        return {"connector": connector_type, "items": items}

    if connector_type == "zoom":
        extra = inst.get("extra") or {}
        client = ZoomClient(
            account_id=inst.get("username"),
            client_id=str(extra.get("client_id") or "").strip(),
            client_secret=inst.get("secret"),
        )
        # List recordings from the last 30 days
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        meetings = await client.list_recordings(from_date=from_date)
        items = [
            {
                "id": str(m.get("id", "")), 
                "name": f"{m.get('topic', 'Untitled Meeting')} ({m.get('start_time', '')[:10]})"
            } 
            for m in meetings 
            if m.get("id")
        ]
        return {"connector": connector_type, "items": items}

    return {"connector": connector_type, "items": []}


async def clear_all_synced_data(session: AsyncSession) -> dict[str, Any]:
    # Vision assets: clear join table first, then assets.
    await session.execute(text("TRUNCATE TABLE chunk_assets RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE document_assets RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE chunks RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE document_permissions RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE documents RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE document_entities RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE entity_relations RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE entity_aliases RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE entities RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE sync_logs RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE query_logs RESTART IDENTITY CASCADE"))
    await session.execute(text("TRUNCATE TABLE ai_task_drafts RESTART IDENTITY CASCADE"))
    await session.commit()

    RAGService.clear_all()
    return {"status": "cleared"}


async def clear_connector_data(session: AsyncSession, connector_type: str) -> dict[str, Any]:
    definition = _get_definition(connector_type)
    await session.execute(text("DELETE FROM documents WHERE source = :s"), {"s": definition.source})
    await session.execute(text("DELETE FROM sync_logs WHERE connector LIKE :p"), {"p": f"{connector_type}:%"})
    await session.commit()
    try:
        RAGService.delete_by_sources([definition.source])
    except Exception as exc:
        log.warning("connectors.clear.vectors_failed", error=str(exc))
    return {"status": "cleared", "connector": connector_type}
