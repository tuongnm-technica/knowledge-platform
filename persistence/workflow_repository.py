from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from storage.db.db import AIWorkflowORM, AIWorkflowNodeORM


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
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            "updated_by": workflow.updated_by,
            "nodes": [
                {
                    "id": str(node.id),
                    "step_order": node.step_order,
                    "name": node.name,
                    "model_override": node.model_override,
                    "system_prompt": node.system_prompt,
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
    ) -> str:
        workflow_id = uuid.uuid4()
        now = datetime.utcnow()
        
        # Create workflow
        workflow = AIWorkflowORM(
            id=workflow_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            created_at=now,
            updated_at=now,
            updated_by=updated_by,
        )
        self._session.add(workflow)

        # Create nodes
        for node_data in nodes:
            node = AIWorkflowNodeORM(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                step_order=node_data.get("step_order", 1),
                name=node_data.get("name", "Step"),
                model_override=node_data.get("model_override"),
                system_prompt=node_data.get("system_prompt", ""),
                updated_at=now,
            )
            self._session.add(node)

        await self._session.commit()
        return str(workflow_id)

    async def update_workflow(
        self,
        workflow_id: str,
        name: str,
        description: str,
        trigger_type: str,
        nodes: list[dict],
        updated_by: str = "system",
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
        workflow.updated_at = now
        workflow.updated_by = updated_by

        # Xóa nodes cũ và thêm mới (Replace all nodes)
        await self._session.execute(
            delete(AIWorkflowNodeORM).where(AIWorkflowNodeORM.workflow_id == uuid.UUID(workflow_id))
        )

        for node_data in nodes:
            node = AIWorkflowNodeORM(
                id=uuid.uuid4(),
                workflow_id=uuid.UUID(workflow_id),
                step_order=node_data.get("step_order", 1),
                name=node_data.get("name", "Step"),
                model_override=node_data.get("model_override"),
                system_prompt=node_data.get("system_prompt", ""),
                updated_at=now,
            )
            self._session.add(node)

        await self._session.commit()
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
