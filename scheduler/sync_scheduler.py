"""
Auto Sync Scheduler
───────────────────
Dùng APScheduler để tự động sync incremental mỗi đêm.

Lịch chạy (múi giờ Asia/Ho_Chi_Minh):
  02:00 AM  → Confluence (chỉ pages được sửa sau last_sync)
  02:30 AM  → Jira       (chỉ issues được update sau last_sync)
  03:00 AM  → Slack      (chỉ messages mới sau last_sync)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from tasks.scanner import scan_and_create_drafts
from sqlalchemy.orm import sessionmaker
from config.settings import settings
import structlog

log = structlog.get_logger()

scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")


async def _run_task_scan() -> None:
    """Scheduler job: quét Slack + Confluence, tạo draft tasks."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from tasks.scanner import scan_and_create_drafts
 
    log.info("scheduler.task_scan.start")
    engine       = create_async_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
 
    try:
        async with SessionLocal() as session:
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

    engine       = create_async_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as session:
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

            # incremental=True → pipeline tự lấy last_sync từ DB
            stats = await pipeline.run(connector, incremental=True)
            log.info("scheduler.sync.done", connector=connector_name, **stats)

    except Exception as e:
        log.error("scheduler.sync.failed", connector=connector_name, error=str(e))
    finally:
        await engine.dispose()


async def sync_confluence(): await _run_sync("confluence")
async def sync_jira():       await _run_sync("jira")
async def sync_slack():      await _run_sync("slack")


def start_scheduler() -> None:
    """Gọi khi FastAPI startup."""
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
        name="Nightly task scan (Slack + Confluence)",
    )
    scheduler.start()
    log.info("scheduler.started", jobs=[
        "confluence @ 02:00 AM",
        "jira       @ 02:30 AM",
        "slack      @ 03:00 AM",
        "task_scan   @ 11:00 PM",
    ])


def stop_scheduler() -> None:
    """Gọi khi FastAPI shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")