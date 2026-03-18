import asyncio
import structlog
from arq import Worker
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from apps.api.services.connectors_service import _run_sync_task
from tasks.scanner import scan_and_create_drafts

log = structlog.get_logger()

async def sync_connector_job(ctx, connector_type: str, instance_id: str, incremental: bool):
    """Task được xử lý ở background, tách bạch hoàn toàn với API server"""
    log.info("worker.sync_connector_job.started", connector=connector_type, instance_id=instance_id)
    try:
        await _run_sync_task(connector_type, instance_id, incremental)
        log.info("worker.sync_connector_job.completed", connector=connector_type, instance_id=instance_id)
    except Exception as e:
        log.error("worker.sync_connector_job.failed", connector=connector_type, error=str(e))
        raise

async def fast_background_job(ctx, task_data: str):
    """Ví dụ một job phụ trợ nhẹ nhàng chạy ở queue default."""
    log.info("worker.fast_job.running", data=task_data)
    return True


async def scan_sources_job(ctx, slack_days: int, confluence_days: int, triggered_by: str, created_by: str | None):
    """ARQ job để quét tất cả các nguồn dữ liệu và tạo task drafts."""
    log.info("worker.scan_sources_job.started", triggered_by=triggered_by)
    async with ctx["db_session_factory"]() as session:
        stats = await scan_and_create_drafts(
            session=session,
            triggered_by=triggered_by,
            created_by=created_by,
            slack_days=slack_days,
            confluence_days=confluence_days,
        )
        log.info("worker.scan_sources_job.completed", **stats)

async def startup(ctx):
    """Khởi tạo các tài nguyên dùng chung cho worker."""
    engine = create_async_engine(settings.DATABASE_URL)
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def shutdown(ctx):
    """Dọn dẹp tài nguyên."""
    await ctx["db_engine"].dispose()

class BaseWorkerSettings:
    """Cấu hình dùng chung cho tất cả các queue"""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    health_check_interval = 60
    on_startup = startup
    on_shutdown = shutdown


class IngestionWorkerSettings(BaseWorkerSettings):
    """Worker chuyên xử lý các tác vụ nặng, tốn thời gian (cào dữ liệu, chunking, embedding)."""
    queue_name = settings.ARQ_INGESTION_QUEUE_NAME
    functions = [sync_connector_job, scan_sources_job]
    job_timeout = settings.ARQ_INGESTION_JOB_TIMEOUT
    max_jobs = settings.ARQ_INGESTION_MAX_JOBS  # Giới hạn chạy song song ít lại để tránh sập GPU/Ollama


class DefaultWorkerSettings(BaseWorkerSettings):
    """Worker xử lý các task nhẹ, ưu tiên cao (gửi thông báo, update db, cache)."""
    queue_name = settings.ARQ_DEFAULT_QUEUE_NAME
    functions = [fast_background_job]
    job_timeout = settings.ARQ_DEFAULT_JOB_TIMEOUT  # Timeout ngắn (2 phút)
    max_jobs = settings.ARQ_DEFAULT_MAX_JOBS      # Cho phép xử lý đồng thời nhiều task nhẹ