import pytest
import uuid
from persistence.workflow_repository import WorkflowRepository
from storage.db.db import AIWorkflowORM, AIWorkflowNodeORM, WorkflowRunORM

@pytest.mark.asyncio
async def test_workflow_repository_create_and_get(db_session):
    repo = WorkflowRepository(db_session)
    
    nodes = [
        {"step_order": 1, "name": "Node 1", "node_type": "llm", "system_prompt": "Prompt 1"},
        {"step_order": 2, "name": "Node 2", "node_type": "rag", "system_prompt": "Prompt 2"}
    ]
    
    # Test Create
    wf_id = await repo.create_workflow(
        name="Test Workflow",
        description="Description",
        trigger_type="manual",
        nodes=nodes,
        updated_by="test_user"
    )
    assert wf_id is not None
    
    # Test Get with Nodes
    workflow = await repo.get_with_nodes(wf_id)
    assert workflow is not None
    assert workflow["name"] == "Test Workflow"
    assert len(workflow["nodes"]) == 2
    assert workflow["nodes"][0]["name"] == "Node 1"
    assert workflow["nodes"][1]["node_type"] == "rag"
    assert workflow["nodes"][1]["step_order"] == 2

@pytest.mark.asyncio
async def test_workflow_repository_list_all(db_session):
    repo = WorkflowRepository(db_session)
    
    await repo.create_workflow("WF 1", "Desc 1", "manual", [{"name": "Step 1", "system_prompt": "S1"}])
    await repo.create_workflow("WF 2", "Desc 2", "scheduled", [{"name": "Step 1", "system_prompt": "S1"}], schedule_cron="0 0 * * *")
    
    workflows = await repo.list_all()
    assert len(workflows) == 2
    # Ordered by created_at desc
    assert workflows[0]["name"] == "WF 2"
    assert workflows[1]["name"] == "WF 1"

@pytest.mark.asyncio
async def test_workflow_repository_update(db_session):
    repo = WorkflowRepository(db_session)
    
    wf_id = await repo.create_workflow("Original", "Desc", "manual", [{"name": "Old Step", "system_prompt": "Old"}])
    
    new_nodes = [
        {"step_order": 1, "name": "New Step 1", "node_type": "llm", "system_prompt": "New 1"},
        {"step_order": 2, "name": "New Step 2", "node_type": "llm", "system_prompt": "New 2"}
    ]
    
    # Test Update
    updated = await repo.update_workflow(
        workflow_id=wf_id,
        name="Updated Name",
        description="Updated Desc",
        trigger_type="webhook",
        nodes=new_nodes,
        webhook_token="secret_token"
    )
    assert updated is True
    
    workflow = await repo.get_with_nodes(wf_id)
    assert workflow["name"] == "Updated Name"
    assert workflow["trigger_type"] == "webhook"
    assert workflow["webhook_token"] == "secret_token"
    assert len(workflow["nodes"]) == 2
    assert workflow["nodes"][0]["name"] == "New Step 1"

@pytest.mark.asyncio
async def test_workflow_repository_delete(db_session):
    repo = WorkflowRepository(db_session)
    
    wf_id = await repo.create_workflow("Delete Me", "Desc", "manual", [{"name": "Step", "system_prompt": "S"}])
    
    # Test Delete
    deleted = await repo.delete_workflow(wf_id)
    assert deleted is True
    
    workflow = await repo.get_with_nodes(wf_id)
    assert workflow is None

@pytest.mark.asyncio
async def test_workflow_run_history(db_session):
    repo = WorkflowRepository(db_session)
    
    wf_id = await repo.create_workflow("WF", "Desc", "manual", [{"name": "S", "system_prompt": "P"}])
    
    # Test Create Run
    run_id = await repo.create_run(
        workflow_id=wf_id,
        triggered_by="user_1",
        trigger_type="manual",
        initial_context="Start context",
        job_id=str(uuid.uuid4())
    )
    assert run_id is not None
    
    # Test Get Run
    run = await repo.get_run(run_id)
    assert run["status"] == "queued"
    assert run["initial_context"] == "Start context"
    
    # Test Update Run Status
    await repo.update_run_status(
        run_id=run_id,
        status="completed",
        node_outputs={"node_1": "Result 1"},
        final_output="Final result"
    )
    
    updated_run = await repo.get_run(run_id)
    assert updated_run["status"] == "completed"
    assert updated_run["node_outputs"] == {"node_1": "Result 1"}
    assert updated_run["final_output"] == "Final result"
    
    # Test List Runs
    runs = await repo.list_runs(wf_id)
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
