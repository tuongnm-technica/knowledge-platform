from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid

from apps.api.auth.dependencies import CurrentUser, get_current_user
from persistence.workflow_repository import WorkflowRepository
from storage.db.db import get_db
from models.chat import ChatJob, ChatSession
from utils.queue_client import get_redis_pool
from config.settings import settings

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ─── Schemas ──────────────────────────────────────────────────────────────────

class WorkflowNodeSchema(BaseModel):
    step_order: int
    name: str
    model_override: Optional[str] = None
    system_prompt: str

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    nodes: List[WorkflowNodeSchema]

class WorkflowUpdateRequest(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    nodes: List[WorkflowNodeSchema]

class WorkflowRunRequest(BaseModel):
    initial_context: str = Field(..., min_length=1)
    session_id: Optional[str] = None

# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_workflows(
    session: AsyncSession = Depends(get_db)
):
    repo = WorkflowRepository(session)
    workflows = await repo.list_all() # Changed from list_workflows to list_all to match existing repo method
    return {"workflows": workflows}


@router.post("/demo", response_model=dict)
async def seed_demo_workflow(session: AsyncSession = Depends(get_db)):
    repo = WorkflowRepository(session)
    # Check if demo exists
    existing = await repo.list_all() # Changed from list_workflows to list_all
    for w in existing:
        if w["name"] == "Demo: Research & Summarize":
            return {"status": "already_exists", "workflow": w}
    
    # Create Demo Workflow
    req = WorkflowCreateRequest(
        name="Demo: Research & Summarize",
        description="Một agent chain gồm 2 bước: 1. Đọc và phân tích thông tin đầu vào. 2. Trích xuất dàn ý và tóm tắt theo gạch đầu dòng.",
        trigger_type="manual",
        nodes=[
            WorkflowNodeSchema( # Changed from WorkflowNodeCreate to WorkflowNodeSchema
                step_order=1,
                name="Analyze Input",
                system_prompt="Bạn là một nhà nghiên cứu. Hãy đọc đoạn văn bản sau và phân tích các ý chính, đưa ra cái nhìn tổng quan ngắn gọn.\n\nVăn bản: {{START}}\n\nPhân tích của bạn:"
            ),
            WorkflowNodeSchema( # Changed from WorkflowNodeCreate to WorkflowNodeSchema
                step_order=2,
                name="Summarize and Format",
                system_prompt="Dựa vào mục tiêu ban đầu là: {{START}}, và bản phân tích sau đây:\n\n{{node_1_output}}\n\nHãy viết một bản tóm tắt hoàn chỉnh trình bày dưới dạng gạch đầu dòng markdown rõ ràng, dễ hiểu."
            )
        ]
    )
    # The create_workflow method in WorkflowRepository expects individual arguments, not a WorkflowCreateRequest object.
    # Also, it expects nodes as a list of dicts.
    workflow_id = await repo.create_workflow(
        name=req.name,
        description=req.description,
        trigger_type=req.trigger_type,
        nodes=[node.dict() for node in req.nodes],
        updated_by="admin",
    )
    # To return the created workflow, we need to fetch it after creation.
    created_workflow = await repo.get_with_nodes(workflow_id)
    return {"status": "created", "workflow": created_workflow}

@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full workflow with its nodes by ID."""
    repo = WorkflowRepository(db)
    row = await repo.get_with_nodes(workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"workflow": row}

@router.post("")
async def create_workflow(
    req: WorkflowCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new AI workflow."""
    if not req.nodes:
        raise HTTPException(status_code=400, detail="Workflow must have at least one node.")
        
    repo = WorkflowRepository(db)
    workflow_id = await repo.create_workflow(
        name=req.name,
        description=req.description,
        trigger_type=req.trigger_type,
        nodes=[node.dict() for node in req.nodes],
        updated_by=user.user_id,
    )
    return {"ok": True, "id": workflow_id}

@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    req: WorkflowUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing AI workflow."""
    if not req.nodes:
        raise HTTPException(status_code=400, detail="Workflow must have at least one node.")
        
    repo = WorkflowRepository(db)
    updated = await repo.update_workflow(
        workflow_id=workflow_id,
        name=req.name,
        description=req.description,
        trigger_type=req.trigger_type,
        nodes=[node.dict() for node in req.nodes],
        updated_by=user.user_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"ok": True, "id": workflow_id}

@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an AI workflow."""
    repo = WorkflowRepository(db)
    deleted = await repo.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"ok": True}

@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    req: WorkflowRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an AI Workflow with initial context."""
    repo = WorkflowRepository(db)
    workflow = await repo.get_with_nodes(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        title = "Workflow: " + workflow.get("name", "Untitled")
        db.add(ChatSession(id=session_id, user_id=user.user_id, title=title))
        await db.flush()

    job_id = str(uuid.uuid4())
    job = ChatJob(
        id=job_id,
        session_id=session_id,
        user_id=user.user_id,
        question=req.initial_context,
        status="queued"
    )
    db.add(job)
    await db.commit()

    import structlog
    log = structlog.get_logger()
    try:
        redis = await get_redis_pool()
        await redis.enqueue_job(
            "run_workflow_job", 
            job_id, 
            user.user_id,
            workflow_id,
            req.initial_context, 
            session_id,
            _queue_name=settings.ARQ_AI_QUEUE_NAME
        )
        log.info("workflow.job_enqueued", job_id=job_id, workflow_id=workflow_id)
    except Exception as e:
        log.error("workflow.enqueue_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue background job")

    return {"ok": True, "job_id": job_id, "session_id": session_id}

