import os
import sys
import asyncio
from arq import Worker
from arq.connections import create_pool
import arq_worker

async def run():
    worker_type = os.getenv("ARQ_WORKER_TYPE", "default")
    
    if worker_type == "ingestion":
        settings_cls = arq_worker.IngestionWorkerSettings
    elif worker_type == "ai":
        settings_cls = arq_worker.AIWorkerSettings
    else:
        settings_cls = arq_worker.DefaultWorkerSettings
        
    sys.stderr.write(f"--- RUN_WORKER BOOTSTRAP ---\n")
    sys.stderr.write(f"WORKER_TYPE: {worker_type}\n")
    sys.stderr.write(f"REDIS_SETTINGS: {settings_cls.redis_settings}\n")
    
    # Create the pool manually to ensure it uses our settings
    pool = await create_pool(settings_cls.redis_settings)
    sys.stderr.write(f"REDIS_POOL CREATED: {pool}\n")
    
    # Use only known valid arguments for arq 0.27.0
    worker = Worker(
        functions=settings_cls.functions,
        redis_pool=pool,
        queue_name=getattr(settings_cls, "queue_name", "arq:queue"),
        health_check_key=getattr(settings_cls, "health_check_key", None),
        on_startup=getattr(settings_cls, "on_startup", None),
        on_shutdown=getattr(settings_cls, "on_shutdown", None),
        on_job_start=getattr(settings_cls, "on_job_start", None),
        on_job_end=getattr(settings_cls, "on_job_end", None),
        job_timeout=getattr(settings_cls, "job_timeout", 300),
        keep_result=getattr(settings_cls, "keep_result", 3600),
        max_jobs=getattr(settings_cls, "max_jobs", 10),
        job_serializer=getattr(settings_cls, "job_serializer", None),
        job_deserializer=getattr(settings_cls, "job_deserializer", None),
        expires_extra_ms=getattr(settings_cls, "expires_extra_ms", 86400000),
        allow_abort_jobs=getattr(settings_cls, "allow_abort_jobs", False),
    )
    
    sys.stderr.write(f"WORKER INITIALIZED, STARTING MAIN LOOP...\n")
    await worker.main()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stderr.write(f"RUN_WORKER CRASHED: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
