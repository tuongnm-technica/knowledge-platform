import pytest
import uuid
from persistence.llm_model_repository import LLMModelRepository
from storage.db.db import LLMModelORM, ModelBindingORM

@pytest.mark.asyncio
async def test_llm_model_repository_create_and_get(db_session):
    repo = LLMModelRepository(db_session)
    
    model_data = {
        "id": uuid.uuid4(),
        "name": "Test Llama",
        "provider": "ollama",
        "llm_model_name": "llama3",
        "is_active": True,
        "is_default": True
    }
    
    # Test Create
    new_model = await repo.create(model_data)
    assert new_model.name == "Test Llama"
    assert new_model.is_default is True
    
    # Test Get by ID
    fetched = await repo.get_by_id(new_model.id)
    assert fetched is not None
    assert fetched.name == "Test Llama"

@pytest.mark.asyncio
async def test_llm_model_repository_list_active(db_session):
    repo = LLMModelRepository(db_session)
    
    # Add one active and one inactive model
    await repo.create({
        "name": "Active Model",
        "provider": "ollama",
        "llm_model_name": "m1",
        "is_active": True
    })
    await repo.create({
        "name": "Inactive Model",
        "provider": "ollama",
        "llm_model_name": "m2",
        "is_active": False
    })
    
    active_models = await repo.list_active()
    assert len(active_models) == 1
    assert active_models[0].name == "Active Model"

@pytest.mark.asyncio
async def test_llm_model_repository_set_binding(db_session):
    repo = LLMModelRepository(db_session)
    
    model = await repo.create({
        "name": "Binder Model",
        "provider": "ollama",
        "llm_model_name": "b1",
        "is_active": True
    })
    
    # Test Set Binding
    binding = await repo.set_binding("chat", model.id)
    assert binding.task_type == "chat"
    assert binding.model_id == model.id
    
    # Test Get Model for Task
    got_model = await repo.get_model_for_task("chat")
    assert got_model.id == model.id
