import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user, require_admin
from persistence.llm_model_repository import LLMModelRepository
from storage.db.db import get_db, reset_llm_models_to_defaults

router = APIRouter(prefix="/models", tags=["models"])

ALLOWED_TASK_TYPES = {"chat", "ingestion_llm", "agent", "embedding", "skill", "vision"}


class LLMModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., pattern="^(gemini|openai|ollama|vllm)$")
    llm_model_name: str = Field(..., min_length=1, max_length=255)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    is_chat_enabled: bool = False
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class LLMModelPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    provider: str
    llm_model_name: str
    base_url: Optional[str] = None
    is_active: bool
    is_default: bool
    is_chat_enabled: bool
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class LLMModelCreate(LLMModelBase):
    pass


class LLMModelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[str] = Field(None, pattern="^(gemini|openai|ollama|vllm)$")
    llm_model_name: Optional[str] = Field(None, min_length=1, max_length=255)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    is_chat_enabled: Optional[bool] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class BindingUpdate(BaseModel):
    model_id: uuid.UUID


class LLMModelResponse(LLMModelBase):
    id: uuid.UUID

    class Config:
        from_attributes = True


@router.get("", response_model=List[LLMModelPublicResponse])
async def list_models(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    repo = LLMModelRepository(db)
    return await repo.list_active()


@router.get("/chat", response_model=List[LLMModelPublicResponse])
async def list_chat_models(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    repo = LLMModelRepository(db)
    return await repo.list_active_for_chat()


@router.get("/admin", response_model=List[LLMModelResponse])
async def list_models_admin(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    repo = LLMModelRepository(db)
    return await repo.list_all()


@router.post("", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    req: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    repo = LLMModelRepository(db)
    return await repo.create(req.model_dump())


@router.patch("/{model_id}", response_model=LLMModelResponse)
async def update_model(
    model_id: uuid.UUID,
    req: LLMModelUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    repo = LLMModelRepository(db)
    updated = await repo.update(model_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return updated


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    repo = LLMModelRepository(db)
    deleted = await repo.delete(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    return None


@router.get("/bindings", response_model=Dict[str, uuid.UUID])
async def get_bindings(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    repo = LLMModelRepository(db)
    return await repo.get_all_bindings()


@router.post("/bindings/{task_type}")
async def set_binding(
    task_type: str,
    req: BindingUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    if task_type not in ALLOWED_TASK_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported task type")

    repo = LLMModelRepository(db)
    model = await repo.get_by_id(req.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if not model.is_active:
        raise HTTPException(status_code=400, detail="Cannot bind an inactive model")

    return await repo.set_binding(task_type, req.model_id)


@router.post("/reset-defaults")
async def reset_models_to_defaults(
    _: CurrentUser = Depends(require_admin),
):
    await reset_llm_models_to_defaults()
    return {"ok": True, "message": "Da khoi phuc cau hinh model mac dinh"}
