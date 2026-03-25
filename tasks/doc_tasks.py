import json
import structlog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.doc_draft_repository import DocDraftRepository
from persistence.project_memory_repository import ProjectMemoryRepository
from orchestration.doc_orchestrator import DocOrchestrator
from orchestration.agent import OllamaLLM

log = structlog.get_logger()

async def run_doc_drafting_job(
    ctx, 
    draft_id: str, 
    system_prompt: str, 
    user_prompt: str, 
    goal: str,
    doc_type: str,
    title: str,
    doc_ids: list[str],
    user_id: str,
    sources: list[dict]
):
    """
    Background job to run the LLM drafting pipeline and update the draft record.
    """
    log.info("worker.doc_drafting.started", draft_id=draft_id, user_id=user_id)
    
    session_factory = ctx["db_session_factory"]
    async with session_factory() as session:
        repo = DocDraftRepository(session)
        memory_repo = ProjectMemoryRepository(session)
        
        llm = OllamaLLM()
        orchestrator = DocOrchestrator(llm)
        
        content = ""
        structured_data = {}
        
        try:
            # Check availability
            if await llm.is_available():
                log.info("worker.doc_drafting.llm_call", draft_id=draft_id)
                raw_content = await orchestrator.generate_document_pipeline(
                    system=system_prompt, 
                    user=user_prompt, 
                    max_tokens=2000
                )
                
                # We need the helper functions from routes/docs.py or recreate them
                # For simplicity, let's assume we can import them or just do basic parsing
                content, structured_data = _parse_llm_response_local(raw_content)
                
                if structured_data:
                    await _extract_and_save_memory_local(structured_data, memory_repo, user_id)
            else:
                log.warning("worker.doc_drafting.llm_unavailable", draft_id=draft_id)
        
        except Exception as e:
            log.error("worker.doc_drafting.failed", draft_id=draft_id, error=str(e))
        
        # Fallback if failed
        if not content:
            from apps.api.routes.docs import _fallback_doc
            content = _fallback_doc(doc_type=doc_type, title=title, question=goal, sources=sources)
            
        # Update Draft
        await repo.update(
            draft_id, 
            content=content, 
            structured_data=structured_data, 
            status="completed"
        )
        log.info("worker.doc_drafting.completed", draft_id=draft_id)

def _parse_llm_response_local(text: str) -> tuple[str, dict]:
    import re
    import json
    pattern = re.compile(r"<json>(.*?)</json>", re.DOTALL)
    match = pattern.search(text)
    structured_data = {}
    if match:
        try:
            structured_data = json.loads(match.group(1).strip())
            text = pattern.sub("", text).strip()
        except Exception:
            pass
    return text.strip(), structured_data

async def _extract_and_save_memory_local(data: dict, repo: ProjectMemoryRepository, user_id: str):
    # Simplified version of the one in docs.py
    for key in ["features", "requirements", "actors", "rules"]:
        items = data.get(key, [])
        if not isinstance(items, list): continue
        for item in items:
            name = item.get("name") or item.get("title")
            desc = item.get("description") or item.get("desc") or str(item)
            if name:
                await repo.upsert(
                    category=key,
                    key=name,
                    value=desc,
                    tags=[key],
                    metadata={"source": "ai_drafting"},
                    created_by=user_id
                )
