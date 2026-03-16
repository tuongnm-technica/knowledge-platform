"""
Auto sync scheduler.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from tasks.scanner import scan_and_create_drafts

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


async def _run_sync(connector_name: str) -> None:
    log.info("scheduler.sync.start", connector=connector_name)

    engine = create_async_engine(settings.DATABASE_URL)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_local() as session:
            from ingestion.pipeline import IngestionPipeline

            pipeline = IngestionPipeline(session)

            if connector_name == "confluence":
                from connectors.confluence.confluence_connector import ConfluenceConnector

                connector = ConfluenceConnector()
            elif connector_name == "jira":
                from connectors.jira.jira_connector import JiraConnector

                connector = JiraConnector()
            elif connector_name == "slack":
                from connectors.slack.slack_connector import SlackConnector

                connector = SlackConnector()
            else:
                log.error("scheduler.unknown_connector", connector=connector_name)
                return

            stats = await pipeline.run(connector, incremental=True)
            log.info("scheduler.sync.done", connector=connector_name, **stats)
    except Exception as e:
        log.error("scheduler.sync.failed", connector=connector_name, error=str(e))
    finally:
        await engine.dispose()


async def sync_confluence():
    await _run_sync("confluence")


async def sync_jira():
    await _run_sync("jira")


async def sync_slack():
    await _run_sync("slack")


def start_scheduler() -> None:
    if scheduler is None or CronTrigger is None:
        log.warning("scheduler.disabled", reason="APScheduler is not installed")
        return

    scheduler.add_job(
        sync_confluence,
        trigger=CronTrigger(hour=2, minute=0),
        id="sync_confluence",
        name="Confluence incremental sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        sync_jira,
        trigger=CronTrigger(hour=2, minute=30),
        id="sync_jira",
        name="Jira incremental sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        sync_slack,
        trigger=CronTrigger(hour=3, minute=0),
        id="sync_slack",
        name="Slack incremental sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_task_scan,
        trigger=CronTrigger(hour=23, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="task_scan_nightly",
        name="Nightly task scan",
    )
    scheduler.start()
    log.info(
        "scheduler.started",
        jobs=[
            "confluence @ 02:00 AM",
            "jira @ 02:30 AM",
            "slack @ 03:00 AM",
            "task_scan @ 11:00 PM",
        ],
    )


def stop_scheduler() -> None:
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
