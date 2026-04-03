import arq
import asyncio
import os
import structlog
from arq import Worker
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from config.settings import settings
from apps.api.services.connectors_service import _run_sync_task


log = structlog.get_logger()

# Lấy URL từ settings, fallback về mặc định cho Docker nếu chưa được định nghĩa
REDIS_URL = getattr(settings, "REDIS_URL", "redis://redis:6379/0")

async def sync_connector_job(ctx, connector_type: str, instance_id: str, incremental: bool, summarize: bool | None = None, relations: bool | None = None, vision: bool | None = None):
    """Task được xử lý ở background, tách bạch hoàn toàn với API server"""
    log.info("worker.sync_connector_job.started", connector=connector_type, instance_id=instance_id)
    log.info("worker.sync_connector_job.dispatching", connector=connector_type, instance_id=instance_id)
    try:
        await _run_sync_task(connector_type, instance_id, incremental, summarize, relations, vision)
        log.info("worker.sync_connector_job.completed", connector=connector_type, instance_id=instance_id)
    except Exception as e:
        log.error("worker.sync_connector_job.failed", connector=connector_type, error=str(e))
        raise

async def run_agent_job_proxy(ctx, *args, **kwargs):
    from orchestration.agent_tasks import run_agent_job
    return await run_agent_job(ctx, *args, **kwargs)

async def run_workflow_job_proxy(ctx, *args, **kwargs):
    from orchestration.agent_tasks import run_workflow_job
    return await run_workflow_job(ctx, *args, **kwargs)

async def run_doc_drafting_job_proxy(ctx, *args, **kwargs):
    from tasks.doc_tasks import run_doc_drafting_job
    return await run_doc_drafting_job(ctx, *args, **kwargs)

async def run_sdlc_generation_job_proxy(ctx, *args, **kwargs):
    from orchestration.sdlc_tasks import run_sdlc_generation_job
    return await run_sdlc_generation_job(ctx, *args, **kwargs)

async def generate_pm_digest_job_proxy(ctx, *args, **kwargs):
    from tasks.pm_reports import generate_pm_digest
    return await generate_pm_digest(ctx, *args, **kwargs)

async def send_scheduled_pm_reports_job_proxy(ctx, *args, **kwargs):
    from tasks.pm_reports import send_scheduled_pm_reports
    return await send_scheduled_pm_reports(ctx, *args, **kwargs)

async def check_daily_logtime_job_proxy(ctx, *args, **kwargs):
    from tasks.pm_logtime import check_daily_logtime
    return await check_daily_logtime(ctx, *args, **kwargs)

async def aggregate_pm_metrics_job(ctx, project_key: str):
    from tasks.pm_metrics import aggregate_pm_metrics
    async with ctx["db_session_factory"]() as session:
        return await aggregate_pm_metrics(session, project_key)


async def fast_background_job(ctx, task_data: str):
    """Ví dụ một job phụ trợ nhẹ nhàng chạy ở queue default."""
    log.info("worker.fast_job.running", data=task_data)
    return True

async def scan_slack_thread_job(ctx, channel_id: str, thread_ts: str, triggered_by: str = "slack_event"):
    """ARQ job để quét 1 thread Slack cụ thể (do webhook gọi)."""
    log.info("worker.scan_slack_thread_job.started", channel_id=channel_id, thread_ts=thread_ts)
    try:
        from tasks.scanners.slack import SlackScanner
        async with ctx["db_session_factory"]() as session:
            from apps.api.services.connectors_service import get_llm_client
            llm_client = await get_llm_client()
            scanner = SlackScanner(session, llm_client)
            await scanner.scan_thread(channel_id, thread_ts, triggered_by=triggered_by)
            log.info("worker.scan_slack_thread_job.completed")
    except Exception as e:
        log.error("worker.scan_slack_thread_job.failed", error=str(e))
        raise



async def scan_sources_job(ctx, slack_days: int, confluence_days: int, triggered_by: str, created_by: str | None):
    """ARQ job để quét tất cả các nguồn dữ liệu và tạo task drafts."""
    log.info("worker.scan_sources_job.started", triggered_by=triggered_by)
    try:
        from tasks.scanner import scan_and_create_drafts
        async with ctx["db_session_factory"]() as session:
            stats = await scan_and_create_drafts(
                session=session,
                triggered_by=triggered_by,
                created_by=created_by,
                slack_days=slack_days,
                confluence_days=confluence_days,
            )
            log.info("worker.scan_sources_job.completed", **stats)
    except Exception as e:
        log.error("worker.scan_sources_job.failed", triggered_by=triggered_by, error=str(e))
        raise

async def handle_job_end(ctx, job_id, function_name, args, kwargs, outcome):
    """Cơ chế Dead Letter Queue (DLQ) đơn giản qua log & Redis"""
    if not outcome.success:
        log.error("worker.job.dead_letter", job_id=job_id, function_name=function_name, exception=str(outcome.result))
        # Tại đây BE Dev có thể gọi session DB: await session.execute("INSERT INTO dead_letter_jobs ...")

async def startup(ctx):
    """Khởi tạo các tài nguyên dùng chung cho worker."""
    log.info("worker.startup", message="Initializing DB connections")
    engine = create_async_engine(settings.DATABASE_URL)
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def shutdown(ctx):
    """Dọn dẹp tài nguyên."""
    log.info("worker.shutdown", message="Disposing DB connections")
    await ctx["db_engine"].dispose()

class BaseWorkerSettings:
    """Cấu hình dùng chung cho tất cả các queue"""
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    health_check_interval = 60
    on_startup = startup
    on_shutdown = shutdown
    after_job = handle_job_end


class IngestionWorkerSettings(BaseWorkerSettings):
    """Worker chuyên xử lý các tác vụ nặng, tốn thời gian (cào dữ liệu, chunking, embedding)."""
    queue_name = settings.ARQ_INGESTION_QUEUE_NAME
    functions = [sync_connector_job, scan_sources_job]
    job_timeout = settings.ARQ_INGESTION_JOB_TIMEOUT
    max_jobs = settings.ARQ_INGESTION_MAX_JOBS  # Giới hạn chạy song song ít lại để tránh sập GPU/Ollama


class DefaultWorkerSettings(BaseWorkerSettings):
    """Worker xử lý các task nhẹ, ưu tiên cao (gửi thông báo, update db, cache)."""
    queue_name = settings.ARQ_DEFAULT_QUEUE_NAME
    functions = [fast_background_job, scan_slack_thread_job]
    job_timeout = settings.ARQ_DEFAULT_JOB_TIMEOUT  # Timeout ngắn (2 phút)
    max_jobs = settings.ARQ_DEFAULT_MAX_JOBS      # Cho phép xử lý đồng thời nhiều task nhẹ


class AIWorkerSettings(BaseWorkerSettings):
    """Worker chuyên xử lý các tác vụ AI/Agent nặng (ReAct loops)."""
    queue_name = "arq:ai"
    functions = [
        arq.func(run_agent_job_proxy, name='run_agent_job'),
        arq.func(run_workflow_job_proxy, name='run_workflow_job'),
        arq.func(run_doc_drafting_job_proxy, name='run_doc_drafting_job'),
        arq.func(run_sdlc_generation_job_proxy, name='run_sdlc_generation_job'),
        arq.func(generate_pm_digest_job_proxy, name='generate_pm_digest'),
        arq.func(send_scheduled_pm_reports_job_proxy, name='send_scheduled_pm_reports'),
        arq.func(check_daily_logtime_job_proxy, name='check_daily_logtime'),
        arq.func(aggregate_pm_metrics_job, name='aggregate_pm_metrics'),
    ]
    job_timeout = settings.ARQ_AI_JOB_TIMEOUT
    max_jobs = 3    # Giới hạn chạy song song ít để bảo vệ GPU