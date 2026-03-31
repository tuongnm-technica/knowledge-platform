import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from storage.db.db import get_db
from apps.api.auth.dependencies import CurrentUser, require_admin
from persistence.llm_model_repository import LLMModelRepository

router = APIRouter(prefix="/models", tags=["models"])

class LLMModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., pattern="^(gemini|openai|ollama|vllm)$")
    llm_model_name: str = Field(..., min_length=1, max_length=255)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

class LLMModelCreate(LLMModelBase):
    pass

class LLMModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    llm_model_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class BindingUpdate(BaseModel):
    model_id: uuid.UUID

class LLMModelResponse(LLMModelBase):
    id: uuid.UUID
    
    class Config:
        from_attributes = True

@router.get("", response_model=List[LLMModelResponse])
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_db) # Any logged in user can see active models
):
    repo = LLMModelRepository(db)
    return await repo.list_active()

@router.get("/admin", response_model=List[LLMModelResponse])
async def list_models_admin(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin)
):
    # This could include inactive models in the future if we filter list_active
    repo = LLMModelRepository(db)
    return await repo.list_active()

@router.post("", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    req: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin)
):
    repo = LLMModelRepository(db)
    return await repo.create(req.model_dump())

@router.patch("/{model_id}", response_model=LLMModelResponse)
async def update_model(
    model_id: uuid.UUID,
    req: LLMModelUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin)
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
    _: CurrentUser = Depends(require_admin)
):
    repo = LLMModelRepository(db)
    await repo.delete(model_id)
    return None

@router.get("/bindings", response_model=Dict[str, uuid.UUID])
async def get_bindings(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin)
):
    repo = LLMModelRepository(db)
    return await repo.get_all_bindings()

@router.post("/bindings/{task_type}")
async def set_binding(
    task_type: str,
    req: BindingUpdate,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin)
):
    repo = LLMModelRepository(db)
    return await repo.set_binding(task_type, req.model_id)
