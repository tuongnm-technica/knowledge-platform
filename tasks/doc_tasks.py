import re
import json
import structlog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.doc_draft_repository import DocDraftRepository
from persistence.project_memory_repository import ProjectMemoryRepository
from orchestration.doc_orchestrator import DocOrchestrator
from services.llm_service import LLMService

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
        
        llm = LLMService(task_type="drafting")
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
                    max_tokens=8192
                )
                
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
    text = text or ""
    structured_data = {}
    
    match = re.search(r"<json>\s*(.*?)\s*</json>", text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1)
        # Clean AI markdown formatting
        json_str = re.sub(r"^```(?:json)?|```$", "", json_str.strip(), flags=re.MULTILINE).strip()
        
        try:
            structured_data = json.loads(json_str)
        except Exception:
            pass
        
        content = text[:match.start()] + text[match.end():]
        content = content.strip()
    else:
        content = text.strip()
        
    return content, structured_data

async def _extract_and_save_memory_local(structured_data: dict, repo: ProjectMemoryRepository, user_id: str):
    if not structured_data:
        return
        
    # 1. Glossary
    for item in structured_data.get("glossary", []):
        if isinstance(item, dict):
            k = item.get("term")
            v = item.get("definition")
            if k and v:
                await repo.upsert(memory_type="glossary", key=k[:255], content=v[:1000], created_by=user_id)
                
    # 2. Stakeholders / Actors
    stakeholders = structured_data.get("stakeholders") or structured_data.get("actors") or []
    for item in stakeholders:
        if isinstance(item, dict):
            k = item.get("name") or item.get("actor")
            v = item.get("role") or item.get("description")
            if k and v:
                await repo.upsert(memory_type="actor", key=k[:255], content=v[:1000], created_by=user_id)

    # 3. Business Rules
    rules = structured_data.get("business_rules") or structured_data.get("rules") or []
    for item in rules:
        if isinstance(item, dict):
            k = item.get("id") or item.get("rule")
            v = item.get("description") or item.get("desc")
            if k and v:
                await repo.upsert(memory_type="rule", key=k[:255], content=v[:1000], created_by=user_id)
