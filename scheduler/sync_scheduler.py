"""
Auto sync scheduler.
"""

import asyncio
import json
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from config.settings import settings
from tasks.scanner import scan_and_create_drafts
from tasks.jira_sync import sync_submitted_drafts

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:  # pragma: no cover - runtime safeguard
    AsyncIOScheduler = None
    CronTrigger = None


log = structlog.get_logger()
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh") if AsyncIOScheduler else None


async def _run_task_scan() -> None:
    log.info("scheduler.task_scan.start")
    engine = create_async_engine(settings.DATABASE_URL)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_local() as session:
            stats = await scan_and_create_drafts(
                session=session,
                triggered_by="scheduler",
                slack_days=1,
                confluence_days=1,
            )
            log.info("scheduler.task_scan.done", **stats)
    except Exception as e:
        log.error("scheduler.task_scan.error", error=str(e))
    finally:
        await engine.dispose()


async def _run_jira_task_sync() -> None:
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        return
    log.info("scheduler.jira_sync.start")
    engine = create_async_engine(settings.DATABASE_URL)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_local() as session:
            stats = await sync_submitted_drafts(session, limit=60)
            log.info("scheduler.jira_sync.done", **stats)
    except Exception as e:
        log.error("scheduler.jira_sync.error", error=str(e))
    finally:
        await engine.dispose()


async def _run_sync_key(connector_key: str) -> None:
    log.info("scheduler.sync.start", connector=connector_key)

    engine = create_async_engine(settings.DATABASE_URL)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_local() as session:
            # Ensure env-backed instances and their connector_configs exist.
            from apps.api.services.connectors_service import build_connector_for_instance, build_connectors_dashboard
            from ingestion.pipeline import IngestionPipeline

            await build_connectors_dashboard(session, can_manage=False)

            selection: dict = {}
            try:
                result = await session.execute(
                    text("SELECT selection FROM connector_configs WHERE connector = :c"),
                    {"c": connector_key},
                )
                raw_selection = result.scalar()
                if isinstance(raw_selection, str):
                    selection = json.loads(raw_selection) if raw_selection else {}
                elif isinstance(raw_selection, dict):
                    selection = raw_selection
            except Exception:
                selection = {}

            if ":" not in str(connector_key or ""):
                return
            connector_type, instance_id = str(connector_key).split(":", 1)
            connector = await build_connector_for_instance(session, connector_type, instance_id, selection)

            pipeline = IngestionPipeline(session)
            stats = await pipeline.run(connector, incremental=True, connector_key=connector_key)
            log.info("scheduler.sync.done", connector=connector_key, **stats)
    except Exception as e:
        log.error("scheduler.sync.failed", connector=connector_key, error=str(e))
    finally:
        await engine.dispose()


async def sync_connector_key_job(connector_key: str) -> None:
    await _run_sync_key(connector_key)


async def refresh_scheduler_jobs() -> None:
    """
    Load connector schedules from DB and update APScheduler jobs.

    Reads connector_configs(auto_sync, schedule_hour, schedule_minute, enabled).
    """
    if scheduler is None or CronTrigger is None:
        return

    engine = create_async_engine(settings.DATABASE_URL)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_local() as session:
            # Ensure env-backed instances and their connector_configs exist.
            from apps.api.services.connectors_service import build_connectors_dashboard

            await build_connectors_dashboard(session, can_manage=False)

            result = await session.execute(
                text(
                    """
                    SELECT connector, enabled, auto_sync, schedule_hour, schedule_minute, schedule_tz
                    FROM connector_configs
                    """
                )
            )
            configs = [dict(row) for row in result.mappings().all()]

        # Replace connector jobs (keep non-connector jobs like task_scan).
        for job in list(scheduler.get_jobs()):
            if str(job.id).startswith("sync_"):
                try:
                    scheduler.remove_job(job.id)
                except Exception:
                    pass

        for cfg in configs:
            connector_key = str(cfg.get("connector") or "").strip()
            if ":" not in connector_key:
                continue

            enabled = bool(cfg.get("enabled", True))
            auto_sync = bool(cfg.get("auto_sync", False))
            hour = cfg.get("schedule_hour")
            minute = cfg.get("schedule_minute")
            tz = cfg.get("schedule_tz") or "Asia/Ho_Chi_Minh"

            if not enabled or not auto_sync or hour is None or minute is None:
                continue

            scheduler.add_job(
                sync_connector_key_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=tz),
                id=f"sync_{connector_key.replace(':', '_')}",
                name=f"{connector_key} incremental sync",
                args=[connector_key],
                replace_existing=True,
                misfire_grace_time=3600,
            )

        log.info("scheduler.jobs_refreshed", jobs=[job.id for job in scheduler.get_jobs()])
    except Exception as exc:
        log.error("scheduler.refresh_failed", error=str(exc))
    finally:
        await engine.dispose()


def trigger_scheduler_refresh() -> None:
    """
    Schedule a background refresh (safe to call from request handlers).
    """
    if scheduler is None:
        return
    try:
        asyncio.get_running_loop().create_task(refresh_scheduler_jobs())
    except RuntimeError:
        # Not in an event loop (e.g., called very early). Ignore.
        return


def start_scheduler() -> None:
    if scheduler is None or CronTrigger is None:
        log.warning("scheduler.disabled", reason="APScheduler is not installed")
        return

    scheduler.add_job(
        _run_task_scan,
        trigger=CronTrigger(hour=23, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="task_scan_nightly",
        name="Nightly task scan",
    )
    scheduler.add_job(
        _run_jira_task_sync,
        trigger=CronTrigger(minute="*/15", timezone="Asia/Ho_Chi_Minh"),
        id="jira_task_sync_15m",
        name="Jira task status sync",
        misfire_grace_time=600,
    )
    scheduler.start()
    trigger_scheduler_refresh()
    log.info(
        "scheduler.started",
        jobs=[
            "task_scan @ 11:00 PM",
        ],
    )


def stop_scheduler() -> None:
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
