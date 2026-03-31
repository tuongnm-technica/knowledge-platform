import uuid
from datetime import datetime
from typing import Dict, List, Optional

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import LLMModelORM, ModelBindingORM

log = structlog.get_logger(__name__)


class LLMModelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> List[LLMModelORM]:
        result = await self.session.execute(
            select(LLMModelORM).order_by(
                LLMModelORM.is_default.desc(),
                LLMModelORM.is_active.desc(),
                LLMModelORM.name.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_active(self) -> List[LLMModelORM]:
        result = await self.session.execute(
            select(LLMModelORM)
            .where(LLMModelORM.is_active == True)
            .order_by(LLMModelORM.is_default.desc(), LLMModelORM.name.asc())
        )
        return list(result.scalars().all())

    async def list_active_for_chat(self) -> List[LLMModelORM]:
        result = await self.session.execute(
            select(LLMModelORM)
            .where(LLMModelORM.is_active == True, LLMModelORM.is_chat_enabled == True)
            .order_by(LLMModelORM.is_default.desc(), LLMModelORM.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, model_id: uuid.UUID | str) -> Optional[LLMModelORM]:
        if isinstance(model_id, str):
            try:
                model_id = uuid.UUID(model_id)
            except ValueError:
                return None
        result = await self.session.execute(select(LLMModelORM).where(LLMModelORM.id == model_id))
        return result.scalar_one_or_none()

    async def get_default(self) -> Optional[LLMModelORM]:
        result = await self.session.execute(
            select(LLMModelORM)
            .where(LLMModelORM.is_active == True, LLMModelORM.is_default == True)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> LLMModelORM:
        if data.get("is_default"):
            await self.session.execute(
                update(LLMModelORM).where(LLMModelORM.is_default == True).values(is_default=False)
            )

        new_model = LLMModelORM(**data)
        self.session.add(new_model)
        await self.session.commit()
        await self.session.refresh(new_model)
        return new_model

    async def update(self, model_id: uuid.UUID | str, data: dict) -> Optional[LLMModelORM]:
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)

        if data.get("is_default"):
            await self.session.execute(
                update(LLMModelORM).where(LLMModelORM.is_default == True).values(is_default=False)
            )

        data["updated_at"] = datetime.utcnow()
        result = await self.session.execute(
            update(LLMModelORM).where(LLMModelORM.id == model_id).values(**data)
        )
        await self.session.commit()
        if result.rowcount == 0:
            return None
        return await self.get_by_id(model_id)

    async def delete(self, model_id: uuid.UUID | str) -> bool:
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)

        result = await self.session.execute(delete(LLMModelORM).where(LLMModelORM.id == model_id))
        await self.session.commit()
        return result.rowcount > 0

    async def get_all_bindings(self) -> Dict[str, uuid.UUID]:
        result = await self.session.execute(select(ModelBindingORM))
        return {binding.task_type: binding.model_id for binding in result.scalars().all()}

    async def set_binding(self, task_type: str, model_id: uuid.UUID | str) -> ModelBindingORM:
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)

        result = await self.session.execute(
            select(ModelBindingORM).where(ModelBindingORM.task_type == task_type)
        )
        binding = result.scalar_one_or_none()

        if binding:
            binding.model_id = model_id
            binding.updated_at = datetime.utcnow()
        else:
            binding = ModelBindingORM(task_type=task_type, model_id=model_id)
            self.session.add(binding)

        await self.session.commit()
        await self.session.refresh(binding)
        return binding

    async def get_model_for_task(self, task_type: str) -> Optional[LLMModelORM]:
        result = await self.session.execute(
            select(ModelBindingORM).where(ModelBindingORM.task_type == task_type)
        )
        binding = result.scalar_one_or_none()

        if binding:
            return await self.get_by_id(binding.model_id)

        return await self.get_default()
