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
from utils.queue_client import get_redis_pool

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:  # pragma: no cover - runtime safeguard
    AsyncIOScheduler = None
    CronTrigger = None


log = structlog.get_logger()
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh") if AsyncIOScheduler else None


async def _run_task_scan() -> None:
    log.info("scheduler.task_scan.enqueue")
    try:
        redis = await get_redis_pool()
        queue_name = settings.ARQ_INGESTION_QUEUE_NAME
        await redis.enqueue_job(
            "scan_sources_job",
            slack_days=1,
            confluence_days=1,
            triggered_by="scheduler",
            created_by=None,
            _queue_name=queue_name
        )
        log.info("scheduler.task_scan.enqueued", queue=queue_name)
    except Exception as e:
        log.error("scheduler.task_scan.enqueue_failed", error=str(e))


async def _run_jira_task_sync() -> None:
    # Reserved for future Jira sync enqueuing if needed. 
    # For now, keeping it consistent.
    log.info("scheduler.jira_sync.skipped", reason="Not yet refactored to worker")

async def _run_pm_digest_generation() -> None:
    """Job hàng ngày lúc 0:00 để AI tự động phân tích dữ liệu mới nhất."""
    try:
        from arq_worker import REDIS_URL
        from arq import create_pool
        from arq.connections import RedisSettings
        
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        # Sử dụng proxy job đã đăng ký trong arq_worker.py
        await pool.enqueue_job("generate_pm_digest_job_proxy", _queue_name="arq:ai")
        log.info("scheduler.pm_digest_gen.enqueued")
    except Exception as exc:
        log.error("scheduler.pm_digest_gen.failed", error=str(exc))

async def _run_pm_report_sending() -> None:
    """Job gửi email báo cáo vào sáng T2 và T5."""
    try:
        from arq_worker import REDIS_URL
        from arq import create_pool
        from arq.connections import RedisSettings
        
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        await pool.enqueue_job("send_scheduled_pm_reports_job_proxy", _queue_name="arq:ai")
        log.info("scheduler.pm_report_send.enqueued")
    except Exception as exc:
        log.error("scheduler.pm_report_send.failed", error=str(exc))

async def _run_daily_logtime_check() -> None:
    """Job hàng ngày lúc 15:00 để quét log time Jira và gửi nhắc nhở."""
    try:
        from arq_worker import REDIS_URL
        from arq import create_pool
        from arq.connections import RedisSettings
        
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        await pool.enqueue_job("check_daily_logtime", _queue_name="arq:ai")
        log.info("scheduler.daily_logtime_check.enqueued")
    except Exception as exc:
        log.error("scheduler.daily_logtime_check.failed", error=str(exc))



async def sync_connector_key_job(connector_key: str) -> None:
    log.info("scheduler.sync.enqueue", connector=connector_key)
    if ":" not in str(connector_key or ""):
        return
    connector_type, instance_id = str(connector_key).split(":", 1)
    
    try:
        redis = await get_redis_pool()
        queue_name = settings.ARQ_INGESTION_QUEUE_NAME
        # We also create a 'running' entry in DB for UI visibility before enqueuing
        # (similar to connectors_service.py pattern)
        # Note: Ideally we'd reuse service logic, but for simplicity we'll just enqueue here.
        await redis.enqueue_job(
            "sync_connector_job",
            connector_type,
            instance_id,
            True, # incremental
            _queue_name=queue_name
        )
        log.info("scheduler.sync.enqueued", connector=connector_key, queue=queue_name)
    except Exception as e:
        log.error("scheduler.sync.enqueue_failed", connector=connector_key, error=str(e))

async def trigger_ai_workflow_job(workflow_id: str) -> None:
    import uuid
    from models.chat import ChatSession, ChatJob
    log.info("scheduler.ai_workflow.enqueue", workflow_id=workflow_id)
    try:
        from storage.db.db import AsyncSessionLocal, AIWorkflowORM
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            # 1. Get workflow to get name
            result = await session.execute(select(AIWorkflowORM).where(AIWorkflowORM.id == uuid.UUID(workflow_id)))
            workflow = result.scalars().first()
            if not workflow:
                return

            # 2. Setup job metadata
            session_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())
            user_id = "scheduler"
            
            # Create chat session & job for tracking
            session.add(ChatSession(id=session_id, user_id=user_id, title=f"Scheduled Workflow: {workflow.name}"))
            session.add(ChatJob(id=job_id, session_id=session_id, user_id=user_id, question="[Scheduled Trigger Run]", status="queued"))
            await session.commit()

            # Create workflow run tracking record
            from persistence.workflow_repository import WorkflowRepository
            repo = WorkflowRepository(session)
            run_id = await repo.create_run(
                workflow_id=workflow_id,
                triggered_by=user_id,
                trigger_type="scheduled",
                initial_context="[Scheduled Trigger Run]",
                job_id=job_id,
            )

        # 3. Enqueue
        redis = await get_redis_pool()
        await redis.enqueue_job(
            "run_workflow_job",
            job_id,
            user_id,
            workflow_id,
            "[Scheduled Trigger Run]",
            session_id,
            run_id,
            _queue_name=settings.ARQ_AI_QUEUE_NAME
        )
        log.info("scheduler.ai_workflow.enqueued", workflow_id=workflow_id)
    except Exception as e:
        import traceback
        log.error("scheduler.ai_workflow.enqueue_failed", workflow_id=workflow_id, error=str(e), trace=traceback.format_exc())


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

            workflow_result = await session.execute(
                text(
                    """
                    SELECT id, name, schedule_cron 
                    FROM ai_workflows 
                    WHERE trigger_type = 'scheduled' AND schedule_cron IS NOT NULL AND schedule_cron != ''
                    """
                )
            )
            scheduled_workflows = [dict(row) for row in workflow_result.mappings().all()]

        # Replace connector & workflow jobs (keep static jobs like task_scan).
        for job in list(scheduler.get_jobs()):
            if str(job.id).startswith("sync_") or str(job.id).startswith("wf_"):
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

        for wf in scheduled_workflows:
            wf_id = str(wf["id"])
            cron_expr = wf["schedule_cron"]
            try:
                scheduler.add_job(
                    trigger_ai_workflow_job,
                    trigger=CronTrigger.from_crontab(cron_expr, timezone="Asia/Ho_Chi_Minh"),
                    id=f"wf_{wf_id}",
                    name=f"Workflow: {wf['name']}",
                    args=[wf_id],
                    replace_existing=True,
                    misfire_grace_time=3600,
                )
            except Exception as e:
                log.warning("scheduler.wf.cron_error", workflow_id=wf_id, cron=cron_expr, error=str(e))

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
        trigger=CronTrigger(hour="8-18", minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="task_scan_hourly",
        name="Hourly task scan during work hours",
    )
    scheduler.add_job(
        _run_jira_task_sync,
        trigger=CronTrigger(minute="*/15", timezone="Asia/Ho_Chi_Minh"),
        id="jira_task_sync_15m",
        name="Jira task status sync",
        misfire_grace_time=600,
    )
    scheduler.add_job(
        _run_pm_digest_generation,
        trigger=CronTrigger(hour=0, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="pm_digest_gen_daily",
        name="Daily PM Digest Generation (0:00)",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_pm_report_sending,
        trigger=CronTrigger(day_of_week="mon,thu", hour=8, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="pm_report_send_biweekly",
        name="Biweekly PM Report Sending (Mon, Thu @ 8:00)",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_daily_logtime_check,
        trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="daily_logtime_reminder",
        name="Daily Jira Log-time Reminder (Mon-Fri @ 15:00)",
        misfire_grace_time=3600,
    )

    scheduler.start()
    trigger_scheduler_refresh()
    log.info(
        "scheduler.started",
        jobs=[
            "task_scan @ Hourly 8-18 (ICT)",
        ],
    )


def stop_scheduler() -> None:
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
