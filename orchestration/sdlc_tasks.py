import uuid
from datetime import datetime
from sqlalchemy import update, select
from storage.db.db import AsyncSessionLocal, SDLCJobORM
from orchestration.agent_workflow import run_sdlc_pipeline
import structlog

log = structlog.get_logger(__name__)

async def run_sdlc_generation_job(ctx, *, job_id: str, user_request: str, user_id: str, context: str = ""):
    """
    Background job to run the Multi-Agent SDLC pipeline.
    """
    log.info("worker.sdlc_job.started", job_id=job_id, user_id=user_id)
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Update status to processing (redundant but good for consistency)
            await session.execute(
                update(SDLCJobORM)
                .where(SDLCJobORM.id == uuid.UUID(job_id))
                .values(status="processing", updated_at=datetime.utcnow())
            )
            await session.commit()

            # 2. Run the actual pipeline
            # Note: run_sdlc_pipeline currently takes (user_request, user_id, session, context)
            final_state = await run_sdlc_pipeline(
                user_request=user_request,
                user_id=user_id,
                session=session,
                context=context
            )

            # 3. Save result
            # LangGraph initial_state contains session, which is not JSON serializable.
            # We need to clean up the state before saving.
            serializable_result = {k: v for k, v in final_state.items() if k != "session"}

            await session.execute(
                update(SDLCJobORM)
                .where(SDLCJobORM.id == uuid.UUID(job_id))
                .values(
                    status="completed",
                    result=serializable_result,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            log.info("worker.sdlc_job.completed", job_id=job_id)

        except Exception as e:
            log.exception("worker.sdlc_job.failed", job_id=job_id, error=str(e))
            await session.execute(
                update(SDLCJobORM)
                .where(SDLCJobORM.id == uuid.UUID(job_id))
                .values(
                    status="failed",
                    error=str(e),
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
