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

async def run_agent_job(ctx: Dict[str, Any], job_id: str, user_id: str, question: str, session_id: str | None = None, llm_model_id: str | None = None):
    """
    Background worker task to execute the Agent reasoning loop.
    Updates the ChatJob object in the database as it progresses.
    """
    log.info("worker.run_agent_job.started", job_id=job_id, user_id=user_id, llm_model_id=llm_model_id)
    
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

            agent = Agent(session, user_id, session_id=session_id, model_id=llm_model_id)
            result = await agent.ask(question, on_thought=on_thought, on_token=on_token, on_sources=on_sources)
            
            # 4. Save the result
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            agent_plan = result.get("agent_plan", [])
            rewritten_query = result.get("rewritten_query", "")
            
            
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




async def run_workflow_job(ctx: Dict[str, Any], job_id: str, user_id: str, workflow_id: str, initial_context: str, session_id: str | None = None, run_id: str | None = None):
    """
    Background worker task to execute an AI Workflow sequentially.
    Supports node_type: llm (default), rag (RAG-augmented), doc_writer.
    Tracks execution in workflow_runs table if run_id is provided.
    """
    log.info("worker.run_workflow_job.started", job_id=job_id, workflow_id=workflow_id, run_id=run_id)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE chat_jobs SET status = 'running', updated_at = NOW() WHERE id = :id"),
            {"id": job_id}
        )
        await session.commit()

        # Update run status to running
        if run_id:
            try:
                from persistence.workflow_repository import WorkflowRepository
                run_repo = WorkflowRepository(session)
                await run_repo.update_run_status(run_id, "running")
            except Exception as e:
                log.warning("worker.run_workflow_job.run_status_update_failed", error=str(e))

        try:
            from persistence.workflow_repository import WorkflowRepository
            repo = WorkflowRepository(session)
            workflow = await repo.get_with_nodes(workflow_id)
            if not workflow or not workflow.get("nodes"):
                raise ValueError(f"Workflow {workflow_id} not found or has no nodes")

            from services.llm_service import LLMService
            llm = LLMService(task_type="workflow")

            payloads = {"START": initial_context}
            node_outputs: Dict[str, str] = {}
            final_output = ""

            async def update_thought(step: str, step_order: int = 0):
                async with AsyncSessionLocal() as s_inner:
                    await s_inner.execute(
                        text("""
                            UPDATE chat_jobs
                            SET thoughts = COALESCE(thoughts, '[]'::jsonb) || :t::jsonb,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": job_id, "t": json.dumps([{"plan": f"[Bước {step_order}] {step}", "step": step_order}])}
                    )
                    await s_inner.commit()

            for node in workflow["nodes"]:
                step_name = node.get("name", "Step")
                step_order = node.get("step_order", 1)
                node_type = node.get("node_type", "llm")

                await update_thought(step_name, step_order)

                prompt_template = node.get("system_prompt", "")

                # Simple templating {{k}}
                for k, v in payloads.items():
                    prompt_template = prompt_template.replace(f"{{{{{k}}}}}", str(v))

                sys_prompt = "You are an AI assistant executing a systematic workflow step. Respond exactly as instructed."
                if node_type == "doc_writer":
                    sys_prompt = (
                        "You are an expert Technical Writer and Business Analyst. "
                        "Your task is to produce a high-quality, professional document based on the provided requirements. "
                        "CRITICAL INSTRUCTIONS:\n"
                        "1. Output ONLY the raw Markdown text.\n"
                        "2. Do NOT wrap your response in an outer markdown code block (like ```markdown).\n"
                        "3. Use appropriate heading levels (#, ##, ###), lists, and tables where suitable.\n"
                        "4. Do NOT include any conversational filler like 'Here is the document' or 'Certainly!'."
                    )
                rag_context = ""

                # ── RAG Node: inject knowledge base context ─────────────────
                if node_type == "rag":
                    try:
                        from retrieval.hybrid.hybrid_search import HybridSearch
                        searcher = HybridSearch(session)
                        # Use the previous node's interpolated output as search query if available, 
                        # otherwise fallback to initial context
                        prev_node_key = f"node_{step_order - 1}_output"
                        search_query = payloads.get(prev_node_key, initial_context)[:500]
                        results = await searcher.search(search_query, top_k=5, allowed_document_ids=None)
                        if results:
                            rag_context = "\n\n".join([
                                f"--- {r.get('title', 'Document')} ---\n{r.get('content', '')[:2000]}"
                                for r in results[:5]
                            ])
                            prompt_template = f"## Thông tin từ Knowledge Base:\n{rag_context}\n\n## Yêu cầu:\n{prompt_template}"
                        log.info("worker.run_workflow_job.rag_node", results=len(results), step=step_name)
                    except Exception as rag_err:
                        log.warning("worker.run_workflow_job.rag_failed", error=str(rag_err))

                model_override = node.get("model_override")
                kw = {}
                if model_override:
                    kw["model"] = model_override

                output = await llm.chat(system=sys_prompt, user=prompt_template, max_tokens=4000, **kw)
                output = (output or "").strip()

                node_key = f"node_{step_order}_output"
                payloads[node_key] = output
                node_outputs[node_key] = output
                final_output = output

                # Save node output to chat job thoughts for live tracking
                async with AsyncSessionLocal() as s_inner:
                    await s_inner.execute(
                        text("""
                            UPDATE chat_jobs
                            SET thoughts = COALESCE(thoughts, '[]'::jsonb) || :t::jsonb,
                                updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": job_id, "t": json.dumps([{
                            "step": "node_complete",
                            "node": step_name,
                            "step_order": step_order,
                            "output_preview": output[:200],
                        }])}
                    )
                    await s_inner.commit()

            # ── Save ChatMessage ─────────────────────────────────────────────
            if session_id:
                new_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=final_output
                )
                session.add(new_msg)

            result_json = {
                "answer": final_output,
                "workflow_name": workflow["name"],
                "node_outputs": node_outputs,
                "sources": [],
            }
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

            # Update workflow_runs record
            if run_id:
                try:
                    run_repo = WorkflowRepository(session)
                    await run_repo.update_run_status(
                        run_id,
                        status="completed",
                        node_outputs=node_outputs,
                        final_output=final_output,
                    )
                except Exception as e:
                    log.warning("worker.run_workflow_job.run_complete_update_failed", error=str(e))

            log.info("worker.run_workflow_job.completed", job_id=job_id, nodes=len(node_outputs))

        except Exception as e:
            import traceback
            trace_err = traceback.format_exc()
            log.exception("worker.run_workflow_job.failed", job_id=job_id, error=str(e), trace=trace_err)
            err_msg = f"{str(e)}\n\n{trace_err}"
            await session.execute(
                text("UPDATE chat_jobs SET status = 'failed', error = :err, updated_at = NOW() WHERE id = :id"),
                {"id": job_id, "err": err_msg}
            )
            await session.commit()
            # Update run record to failed
            if run_id:
                try:
                    run_repo = WorkflowRepository(session)
                    await run_repo.update_run_status(run_id, status="failed", error=str(e))
                except Exception:
                    pass

            await session.commit()


