from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import AIWorkflowORM, AIWorkflowNodeORM, WorkflowRunORM


class WorkflowRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── Read ─────────────────────────────────────────────────────────────────

    async def list_all(self) -> list[dict]:
        """Return all workflows ordered by creation date."""
        result = await self._session.execute(
            select(AIWorkflowORM).order_by(AIWorkflowORM.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "name": row.name,
                "description": row.description,
                "trigger_type": row.trigger_type,
                "schedule_cron": row.schedule_cron,
                "webhook_token": row.webhook_token,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "updated_by": row.updated_by,
            }
            for row in rows
        ]

    async def get_with_nodes(self, workflow_id: str) -> dict | None:
        """Return a single workflow along with its ordered nodes."""
        result = await self._session.execute(
            select(AIWorkflowORM).where(AIWorkflowORM.id == uuid.UUID(workflow_id))
        )
        workflow = result.scalars().first()
        if not workflow:
            return None

        nodes_result = await self._session.execute(
            select(AIWorkflowNodeORM)
            .where(AIWorkflowNodeORM.workflow_id == uuid.UUID(workflow_id))
            .order_by(AIWorkflowNodeORM.step_order.asc())
        )
        nodes = nodes_result.scalars().all()

        return {
            "id": str(workflow.id),
            "name": workflow.name,
            "description": workflow.description,
            "trigger_type": workflow.trigger_type,
            "schedule_cron": workflow.schedule_cron,
            "webhook_token": workflow.webhook_token,
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            "updated_by": workflow.updated_by,
            "nodes": [
                {
                    "id": str(node.id),
                    "step_order": node.step_order,
                    "name": node.name,
                    "node_type": node.node_type or "llm",
                    "model_override": node.model_override,
                    "system_prompt": node.system_prompt,
                    "input_vars": node.input_vars or [],
                }
                for node in nodes
            ],
        }

    # ─── Write ────────────────────────────────────────────────────────────────

    async def create_workflow(
        self,
        name: str,
        description: str,
        trigger_type: str,
        nodes: list[dict],
        updated_by: str = "system",
        schedule_cron: Optional[str] = None,
        webhook_token: Optional[str] = None,
    ) -> str:
        workflow_id = uuid.uuid4()
        now = datetime.utcnow()

        workflow = AIWorkflowORM(
            id=workflow_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            schedule_cron=schedule_cron,
            webhook_token=webhook_token,
            created_at=now,
            updated_at=now,
            updated_by=updated_by,
        )
        self._session.add(workflow)

        for node_data in nodes:
            node = AIWorkflowNodeORM(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                step_order=node_data.get("step_order", 1),
                name=node_data.get("name", "Step"),
                node_type=node_data.get("node_type", "llm"),
                model_override=node_data.get("model_override"),
                system_prompt=node_data.get("system_prompt", ""),
                input_vars=node_data.get("input_vars", []),
                updated_at=now,
            )
            self._session.add(node)

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return str(workflow_id)

    async def update_workflow(
        self,
        workflow_id: str,
        name: str,
        description: str,
        trigger_type: str,
        nodes: list[dict],
        updated_by: str = "system",
        schedule_cron: Optional[str] = None,
        webhook_token: Optional[str] = None,
    ) -> bool:
        result = await self._session.execute(
            select(AIWorkflowORM).where(AIWorkflowORM.id == uuid.UUID(workflow_id))
        )
        workflow = result.scalars().first()
        if not workflow:
            return False

        now = datetime.utcnow()
        workflow.name = name
        workflow.description = description
        workflow.trigger_type = trigger_type
        workflow.schedule_cron = schedule_cron
        workflow.webhook_token = webhook_token
        workflow.updated_at = now
        workflow.updated_by = updated_by

        # Xóa nodes cũ và thêm mới (replace strategy)
        await self._session.execute(
            delete(AIWorkflowNodeORM).where(AIWorkflowNodeORM.workflow_id == uuid.UUID(workflow_id))
        )

        for node_data in nodes:
            node = AIWorkflowNodeORM(
                id=uuid.uuid4(),
                workflow_id=uuid.UUID(workflow_id),
                step_order=node_data.get("step_order", 1),
                name=node_data.get("name", "Step"),
                node_type=node_data.get("node_type", "llm"),
                model_override=node_data.get("model_override"),
                system_prompt=node_data.get("system_prompt", ""),
                input_vars=node_data.get("input_vars", []),
                updated_at=now,
            )
            self._session.add(node)

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return True

    async def delete_workflow(self, workflow_id: str) -> bool:
        result = await self._session.execute(
            select(AIWorkflowORM).where(AIWorkflowORM.id == uuid.UUID(workflow_id))
        )
        workflow = result.scalars().first()
        if not workflow:
            return False

        await self._session.delete(workflow)
        await self._session.commit()
        return True

    # ─── Workflow Runs ────────────────────────────────────────────────────────

    async def create_run(
        self,
        workflow_id: str,
        triggered_by: str,
        trigger_type: str = "manual",
        initial_context: str = "",
        job_id: Optional[str] = None,
    ) -> str:
        run_id = uuid.uuid4()
        run = WorkflowRunORM(
            id=run_id,
            workflow_id=uuid.UUID(workflow_id),
            job_id=uuid.UUID(job_id) if job_id else None,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            status="queued",
            initial_context=initial_context,
            node_outputs={},
            created_at=datetime.utcnow(),
        )
        self._session.add(run)
        await self._session.commit()
        return str(run_id)

    async def update_run_status(
        self,
        run_id: str,
        status: str,
        node_outputs: Optional[dict] = None,
        final_output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        result = await self._session.execute(
            select(WorkflowRunORM).where(WorkflowRunORM.id == uuid.UUID(run_id))
        )
        run = result.scalars().first()
        if not run:
            return
        run.status = status
        if node_outputs is not None:
            run.node_outputs = node_outputs
        if final_output is not None:
            run.final_output = final_output
        if error is not None:
            run.error = error
        if status == "running" and not run.started_at:
            run.started_at = datetime.utcnow()
        if status in ("completed", "failed"):
            run.finished_at = datetime.utcnow()
        await self._session.commit()

    async def list_runs(self, workflow_id: str, limit: int = 20) -> list[dict]:
        """Return recent runs for a workflow."""
        result = await self._session.execute(
            select(WorkflowRunORM)
            .where(WorkflowRunORM.workflow_id == uuid.UUID(workflow_id))
            .order_by(WorkflowRunORM.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "workflow_id": str(row.workflow_id),
                "job_id": str(row.job_id) if row.job_id else None,
                "triggered_by": row.triggered_by,
                "trigger_type": row.trigger_type,
                "status": row.status,
                "initial_context": (row.initial_context or "")[:200],  # truncate for listing
                "node_outputs": row.node_outputs or {},
                "final_output": row.final_output,
                "error": row.error,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def get_run(self, run_id: str) -> dict | None:
        """Get a specific run with full node outputs."""
        result = await self._session.execute(
            select(WorkflowRunORM).where(WorkflowRunORM.id == uuid.UUID(run_id))
        )
        row = result.scalars().first()
        if not row:
            return None
        return {
            "id": str(row.id),
            "workflow_id": str(row.workflow_id),
            "job_id": str(row.job_id) if row.job_id else None,
            "triggered_by": row.triggered_by,
            "trigger_type": row.trigger_type,
            "status": row.status,
            "initial_context": row.initial_context,
            "node_outputs": row.node_outputs or {},
            "final_output": row.final_output,
            "error": row.error,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
