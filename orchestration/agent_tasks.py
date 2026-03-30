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
                    # 1. Append thought to the list (using COALESCE to avoid NULL issues)
                    await session_inner.execute(
                        text("""
                            UPDATE chat_jobs 
                            SET thoughts = COALESCE(thoughts, '[]'::jsonb) || :t::jsonb, 
                                updated_at = NOW() 
                            WHERE id = :id
                        """),
                        {"id": job_id, "t": json.dumps([thought_data])}
                    )
                    
                    # 2. If it contains a plan or rewritten query, update result immediately
                    if "plan" in thought_data or "rewritten_query" in thought_data:
                        update_parts = []
                        params = {"id": job_id}
                        
                        if "plan" in thought_data:
                            update_parts.append("result = jsonb_set(COALESCE(result, '{}'::jsonb), '{agent_plan}', :p::jsonb)")
                            params["p"] = json.dumps(thought_data["plan"])
                            
                        if "rewritten_query" in thought_data:
                            update_parts.append("result = jsonb_set(COALESCE(result, '{}'::jsonb), '{rewritten_query}', to_jsonb(:rq))")
                            params["rq"] = thought_data["rewritten_query"]
                            
                        if update_parts:
                            await session_inner.execute(
                                text(f"UPDATE chat_jobs SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = :id"),
                                params
                            )
                    
                    await session_inner.commit()

            current_answer_list = [""]
            last_db_at = [0.0]

            async def on_token(token: str):
                import time
                current_answer_list[0] += token
                now = time.time()
                
                # Batch updates: update only every 15 characters OR every 1.5 seconds
                if len(current_answer_list[0]) % 15 == 0 or (now - last_db_at[0]) > 1.5:
                    last_db_at[0] = now
                    async with AsyncSessionLocal() as session_inner:
                        await session_inner.execute(
                            text("""
                                UPDATE chat_jobs 
                                SET result = jsonb_set(COALESCE(result, '{}'::jsonb), '{answer}', to_jsonb(:ans)),
                                    updated_at = NOW()
                                WHERE id = :id
                            """),
                            {"id": job_id, "ans": current_answer_list[0]}
                        )
                        await session_inner.commit()

            async def on_sources(sources: list[dict]):
                async with AsyncSessionLocal() as session_inner:
                    await session_inner.execute(
                        text("""
                            UPDATE chat_jobs 
                            SET result = jsonb_set(COALESCE(result, '{}'::jsonb), '{sources}', :s::jsonb),
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": job_id, "s": json.dumps(sources)}
                    )
                    await session_inner.commit()

            agent = Agent(session, user_id)
            result = await agent.ask(question, on_thought=on_thought, on_token=on_token, on_sources=on_sources)
            
            # 4. Save the result
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            agent_plan = result.get("agent_plan", [])
            rewritten_query = result.get("rewritten_query", "")
            
            # Create the final assistant message in the session
            if session_id:
                new_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=answer,
                    sources=sources,
                    agent_plan=agent_plan,
                    rewritten_query=rewritten_query
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
                    "res": json.dumps(result)
                }
            )
            print("=== WORKER TRACE ===")
            print("Agent Result keys:", list(result.keys()))
            if "agent_plan" in result:
                print("agent_plan value length:", len(result["agent_plan"]))
            else:
                print("agent_plan is literally missing from loop return!")
            print("====================")
            await session.commit()
            log.info("worker.run_agent_job.completed", job_id=job_id)

        except Exception as e:
            log.exception("worker.run_agent_job.failed", job_id=job_id, error=str(e))
            await session.execute(
                text("UPDATE chat_jobs SET status = 'failed', error = :err, updated_at = NOW() WHERE id = :id"),
                {"id": job_id, "err": str(e)}
            )
            await session.commit()


async def run_workflow_job(ctx: Dict[str, Any], job_id: str, user_id: str, workflow_id: str, initial_context: str, session_id: str | None = None):
    """
    Background worker task to execute an AI Workflow sequentially.
    """
    log.info("worker.run_workflow_job.started", job_id=job_id, workflow_id=workflow_id)
    
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE chat_jobs SET status = 'running', updated_at = NOW() WHERE id = :id"),
            {"id": job_id}
        )
        await session.commit()
        
        try:
            from persistence.workflow_repository import WorkflowRepository
            repo = WorkflowRepository(session)
            workflow = await repo.get_with_nodes(workflow_id)
            if not workflow or not workflow.get("nodes"):
                raise ValueError(f"Workflow {workflow_id} not found or has no nodes")

            from llm.ollama import OllamaLLMClient
            llm = OllamaLLMClient()
            
            payloads = {"START": initial_context}
            final_output = ""
            
            async def update_thought(step: str):
                async with AsyncSessionLocal() as s_inner:
                    await s_inner.execute(
                        text("""
                            UPDATE chat_jobs 
                            SET thoughts = COALESCE(thoughts, '[]'::jsonb) || :t::jsonb, 
                                updated_at = NOW() 
                            WHERE id = :id
                        """),
                        {"id": job_id, "t": json.dumps([{"plan": f"Executing: {step}"}])}
                    )
                    await s_inner.commit()

            for node in workflow["nodes"]:
                step_name = node.get("name", "Step")
                await update_thought(step_name)
                
                prompt = node.get("system_prompt", "")
                
                # Simple templating {{k}}
                for k, v in payloads.items():
                    prompt = prompt.replace(f"{{{{{k}}}}}", str(v))
                
                # Provide a generic User prompt representing the task
                sys_prompt = "You are an AI assistant executing a systematic workflow step. Respond exactly as instructed."
                user_prompt = prompt
                
                model_override = node.get("model_override")
                kw = {}
                if model_override:
                    kw["model"] = model_override
                    
                output = await llm.chat(system=sys_prompt, user=user_prompt, max_tokens=3000, **kw)
                output = (output or "").strip()
                
                payloads[f"node_{node.get('step_order', 1)}_output"] = output
                final_output = output
                
            if session_id:
                new_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=final_output
                )
                session.add(new_msg)
                
            result_json = {"answer": final_output, "workflow_name": workflow["name"]}
            await session.execute(
                text("""
                    UPDATE chat_jobs 
                    SET status = 'completed', 
                        result = :res, 
                        updated_at = NOW() 
                    WHERE id = :id
                """),
                {"id": job_id, "res": json.dumps(result_json)}
            )
            await session.commit()
            log.info("worker.run_workflow_job.completed", job_id=job_id)

        except Exception as e:
            import traceback
            trace_err = traceback.format_exc()
            log.exception("worker.run_workflow_job.failed", job_id=job_id, error=str(e), trace=trace_err)
            await session.execute(
                text("UPDATE chat_jobs SET status = 'failed', error = :err, updated_at = NOW() WHERE id = :id"),
                {"id": job_id, "err": f"{str(e)}\n\n{trace_err}"}
            )
            await session.commit()


