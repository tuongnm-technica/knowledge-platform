import asyncio
import structlog
from arq import Worker
from arq.connections import RedisSettings

from config.settings import settings
from apps.api.services.connectors_service import _run_sync_task

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

class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [sync_connector_job]
    
    # Tuỳ chọn: bạn có thể định nghĩa cron jobs của arq ở đây để chạy scheduler
    # cron_jobs = [cron(run_scheduled_tasks, hour={2,3,4}, minute=0)]
    
    max_jobs = 5 # Giới hạn concurrency để không ngốn sạch CPU