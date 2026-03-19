import asyncio
import json
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Any, Dict, List

from orchestration.agent import Agent
from storage.db.db import AsyncSessionLocal
from models.chat import ChatJob, ChatMessage

log = structlog.get_logger(__name__)

async def run_agent_job(ctx: Dict[str, Any], job_id: str, user_id: str, question: str, session_id: str | None = None):
    """
    Background worker task to execute the Agent reasoning loop.
    Updates the ChatJob object in the database as it progresses.
    """
    log.info("worker.run_agent_job.started", job_id=job_id, user_id=user_id)
    
    async with AsyncSessionLocal() as session:
        # 1. Update status to 'running'
        await session.execute(
            text("UPDATE chat_jobs SET status = 'running', updated_at = NOW() WHERE id = :id"),
            {"id": job_id}
        )
        await session.commit()
        
        try:
            # 2. Check/Create chat session if needed
            if not session_id:
                # This could be handled here or in the API layer. 
                # For now, let's assume session_id is provided or we can create a default one.
                pass

            # 3. Initialize Agent with a custom thought recorder
            async def on_thought(thought_data: dict):
                async with AsyncSessionLocal() as session_inner:
                    # Append thought to the list
                    await session_inner.execute(
                        text("""
                            UPDATE chat_jobs 
                            SET thoughts = thoughts || :t::jsonb, 
                                updated_at = NOW() 
                            WHERE id = :id
                        """),
                        {"id": job_id, "t": json.dumps([thought_data])}
                    )
                    await session_inner.commit()

            agent = Agent(session, user_id)
            result = await agent.ask(question, on_thought=on_thought)
            
            # 4. Save the result
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            
            # Create the final assistant message in the session
            if session_id:
                new_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=answer,
                    sources=sources
                )
                session.add(new_msg)
            
            # 5. Update job to 'completed'
            await session.execute(
                text("""
                    UPDATE chat_jobs 
                    SET status = 'completed', 
                        result = :res, 
                        updated_at = NOW() 
                    WHERE id = :id
                """),
                {
                    "id": job_id, 
                    "res": json.dumps({"answer": answer, "sources": sources})
                }
            )
            await session.commit()
            log.info("worker.run_agent_job.completed", job_id=job_id)

        except Exception as e:
            log.exception("worker.run_agent_job.failed", job_id=job_id, error=str(e))
            await session.execute(
                text("UPDATE chat_jobs SET status = 'failed', error = :err, updated_at = NOW() WHERE id = :id"),
                {"id": job_id, "err": str(e)}
            )
            await session.commit()

