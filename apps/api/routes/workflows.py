from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
import secrets

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
    node_type: str = "llm"  # llm | rag | doc_writer
    model_override: Optional[str] = None
    system_prompt: str
    input_vars: List[str] = []

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"   # manual | scheduled | webhook
    schedule_cron: Optional[str] = None
    nodes: List[WorkflowNodeSchema]

class WorkflowUpdateRequest(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    schedule_cron: Optional[str] = None
    nodes: List[WorkflowNodeSchema]

class WorkflowRunRequest(BaseModel):
    initial_context: str = Field(..., min_length=1)
    session_id: Optional[str] = None

# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_workflows(
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user)
):
    repo = WorkflowRepository(session)
    workflows = await repo.list_all()
    return {"workflows": workflows}


@router.post("/demo", response_model=dict)
async def seed_demo_workflow(session: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    repo = WorkflowRepository(session)
    existing = await repo.list_all()
    for w in existing:
        if w["name"] == "Demo: Research & Summarize":
            return {"status": "already_exists", "workflow": w}

    workflow_id = await repo.create_workflow(
        name="Demo: Research & Summarize",
        description="Một agent chain gồm 2 bước: 1. Đọc và phân tích thông tin đầu vào. 2. Trích xuất dàn ý và tóm tắt theo gạch đầu dòng.",
        trigger_type="manual",
        nodes=[
            {
                "step_order": 1,
                "name": "Analyze Input",
                "node_type": "llm",
                "system_prompt": "Bạn là một nhà nghiên cứu. Hãy đọc đoạn văn bản sau và phân tích các ý chính, đưa ra cái nhìn tổng quan ngắn gọn.\n\nVăn bản: {{START}}\n\nPhân tích của bạn:",
            },
            {
                "step_order": 2,
                "name": "Summarize and Format",
                "node_type": "llm",
                "system_prompt": "Dựa vào mục tiêu ban đầu là: {{START}}, và bản phân tích sau đây:\n\n{{node_1_output}}\n\nHãy viết một bản tóm tắt hoàn chỉnh trình bày dưới dạng gạch đầu dòng markdown rõ ràng, dễ hiểu.",
            }
        ],
        updated_by=user.user_id,
    )
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

    webhook_token = None
    if req.trigger_type == "webhook":
        webhook_token = secrets.token_urlsafe(32)

    repo = WorkflowRepository(db)
    workflow_id = await repo.create_workflow(
        name=req.name,
        description=req.description,
        trigger_type=req.trigger_type,
        nodes=[node.dict() for node in req.nodes],
        updated_by=user.user_id,
        schedule_cron=req.schedule_cron,
        webhook_token=webhook_token,
    )
    return {"ok": True, "id": workflow_id, "webhook_token": webhook_token}


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
    # Preserve existing webhook_token if trigger_type remains webhook
    existing = await repo.get_with_nodes(workflow_id)
    webhook_token = existing.get("webhook_token") if existing else None
    if req.trigger_type == "webhook" and not webhook_token:
        webhook_token = secrets.token_urlsafe(32)

    updated = await repo.update_workflow(
        workflow_id=workflow_id,
        name=req.name,
        description=req.description,
        trigger_type=req.trigger_type,
        nodes=[node.dict() for node in req.nodes],
        updated_by=user.user_id,
        schedule_cron=req.schedule_cron,
        webhook_token=webhook_token,
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

    # Create run record for history tracking
    run_id = await repo.create_run(
        workflow_id=workflow_id,
        triggered_by=user.user_id,
        trigger_type="manual",
        initial_context=req.initial_context,
        job_id=job_id,
    )

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
            run_id,  # Pass run_id for history tracking
            _queue_name=settings.ARQ_AI_QUEUE_NAME
        )
        log.info("workflow.job_enqueued", job_id=job_id, workflow_id=workflow_id, run_id=run_id)
    except Exception as e:
        log.error("workflow.enqueue_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue background job")

    return {"ok": True, "job_id": job_id, "session_id": session_id, "run_id": run_id}


# ─── Run History Endpoints ────────────────────────────────────────────────────

@router.get("/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    limit: int = 20,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent runs for a workflow."""
    repo = WorkflowRepository(db)
    workflow = await repo.get_with_nodes(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    runs = await repo.list_runs(workflow_id, limit=limit)
    return {"runs": runs}


@router.get("/{workflow_id}/runs/{run_id}")
async def get_workflow_run(
    workflow_id: str,
    run_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific run including node outputs."""
    repo = WorkflowRepository(db)
    run = await repo.get_run(run_id)
    if not run or run["workflow_id"] != workflow_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    return {"run": run}


# ─── Webhook Trigger ──────────────────────────────────────────────────────────

@router.post("/webhook/{token}")
async def webhook_trigger(
    token: str,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
):
    """Public webhook endpoint to trigger a workflow by token."""
    from sqlalchemy import select
    from storage.db.db import AIWorkflowORM
    result = await db.execute(
        select(AIWorkflowORM).where(AIWorkflowORM.webhook_token == token)
    )
    workflow_orm = result.scalars().first()
    if not workflow_orm:
        raise HTTPException(status_code=404, detail="Webhook not found.")

    workflow_id = str(workflow_orm.id)
    initial_context = body.get("context", body.get("text", str(body)))

    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    db.add(ChatSession(id=session_id, user_id="webhook", title=f"Webhook: {workflow_orm.name}"))
    await db.flush()
    db.add(ChatJob(id=job_id, session_id=session_id, user_id="webhook", question=initial_context, status="queued"))
    await db.commit()

    repo = WorkflowRepository(db)
    run_id = await repo.create_run(
        workflow_id=workflow_id,
        triggered_by="webhook",
        trigger_type="webhook",
        initial_context=initial_context,
        job_id=job_id,
    )

    try:
        redis = await get_redis_pool()
        await redis.enqueue_job(
            "run_workflow_job",
            job_id,
            "webhook",
            workflow_id,
            initial_context,
            session_id,
            run_id,
            _queue_name=settings.ARQ_AI_QUEUE_NAME
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue: {e}")

    return {"ok": True, "job_id": job_id, "run_id": run_id}
