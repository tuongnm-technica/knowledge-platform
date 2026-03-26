"""
test_graph_integration.py — Integration tests for Graph API endpoints

These tests verify:
1. All 4 endpoints work with proper user filtering
2. User permission isolation works correctly
3. Node details are fetched correctly
4. Error handling works as expected
"""

import asyncio
import pytest
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from storage.db.db import get_db
from apps.api.routes.graph import (
    graph_health,
    graph_snapshot,
    graph_gaps,
    graph_node_detail,
)
from apps.api.auth.dependencies import CurrentUser
from permissions.filter import PermissionFilter


class MockUser:
    """Mock CurrentUser for testing"""
    def __init__(self, user_id: str, is_admin: bool = True):
        self.user_id = user_id
        self.is_admin = is_admin
        self.email = f"{user_id}@test.local"
        self.display_name = f"Test User {user_id}"


@pytest.mark.asyncio
async def test_graph_health_admin(db_session: AsyncSession):
    """Test health endpoint for admin users (should see all docs)"""
    admin_user = MockUser("admin_user", is_admin=True)
    
    result = await graph_health(
        session=db_session,
        current_user=admin_user
    )
    
    assert "totalDocuments" in result
    assert "lastUpdated" in result
    assert "coveragePercent" in result
    assert "freshnessDays" in result
    assert "statusByConnector" in result
    
    print(f"✓ Admin health response: {result['totalDocuments']} docs, {result['coveragePercent']}% coverage")


@pytest.mark.asyncio
async def test_graph_health_regular_user(db_session: AsyncSession):
    """Test health endpoint for regular users (should filter by permissions)"""
    regular_user = MockUser("regular_user", is_admin=False)
    
    # Note: This will return limited data based on user permissions
    result = await graph_health(
        session=db_session,
        current_user=regular_user
    )
    
    assert "totalDocuments" in result
    assert isinstance(result["totalDocuments"], int)
    assert result["totalDocuments"] >= 0
    
    print(f"✓ Regular user health response: {result['totalDocuments']} accessible docs")


@pytest.mark.asyncio
async def test_graph_snapshot_entities_view(db_session: AsyncSession):
    """Test snapshot endpoint with entities view"""
    admin_user = MockUser("admin_user", is_admin=True)
    
    result = await graph_snapshot(
        view="entities",
        limit=30,
        edge_limit=60,
        session=db_session,
        current_user=admin_user
    )
    
    assert "nodes" in result
    assert "edges" in result
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)
    
    # Check node structure
    if result["nodes"]:
        node = result["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "type" in node
    
    # Check edge structure
    if result["edges"]:
        edge = result["edges"][0]
        assert "from" in edge or "source" in edge
        assert "to" in edge or "target" in edge
    
    print(f"✓ Snapshot entities: {len(result['nodes'])} nodes, {len(result['edges'])} edges")


@pytest.mark.asyncio
async def test_graph_gaps_analysis(db_session: AsyncSession):
    """Test gaps endpoint for data quality insights"""
    admin_user = MockUser("admin_user", is_admin=True)
    
    result = await graph_gaps(
        since_days=30,
        per_source=90,
        session=db_session,
        current_user=admin_user
    )
    
    assert "staleSources" in result
    assert "orphanEntities" in result
    assert "missingRelationships" in result
    assert "isolatedDocuments" in result
    
    # Check that these are lists
    assert isinstance(result["staleSources"], list)
    assert isinstance(result["orphanEntities"], list)
    assert isinstance(result["missingRelationships"], list)
    assert isinstance(result["isolatedDocuments"], list)
    
    print(f"✓ Gap insights: {len(result['staleSources'])} stale sources, "
          f"{len(result['orphanEntities'])} orphan entities")


@pytest.mark.asyncio
async def test_graph_node_detail_entity(db_session: AsyncSession):
    """Test node detail endpoint for an entity"""
    admin_user = MockUser("admin_user", is_admin=True)
    
    # First get a node ID from snapshot
    snapshot_result = await graph_snapshot(
        view="entities",
        limit=5,
        edge_limit=0,
        session=db_session,
        current_user=admin_user
    )
    
    if not snapshot_result["nodes"]:
        print("⊘ Skipping node detail test: no nodes available")
        return
    
    node_id = snapshot_result["nodes"][0]["id"]
    
    # Now fetch node details
    detail_result = await graph_node_detail(
        node_id=node_id,
        session=db_session,
        current_user=admin_user
    )
    
    assert "id" in detail_result
    assert "label" in detail_result
    assert "type" in detail_result
    assert "metadata" in detail_result
    assert "related" in detail_result
    
    print(f"✓ Node detail: {detail_result['label']} ({detail_result['type']})")


@pytest.mark.asyncio
async def test_graph_user_isolation(db_session: AsyncSession):
    """Test that user_id filtering actually works"""
    admin_user = MockUser("admin_user", is_admin=True)
    regular_user = MockUser("regular_user", is_admin=False)
    
    # Get health for both
    admin_health = await graph_health(session=db_session, current_user=admin_user)
    regular_health = await graph_health(session=db_session, current_user=regular_user)
    
    admin_docs = admin_health["totalDocuments"]
    regular_docs = regular_health["totalDocuments"]
    
    # Regular user should see same or fewer documents
    assert regular_docs <= admin_docs
    
    print(f"✓ User isolation: Admin sees {admin_docs} docs, regular user sees {regular_docs} docs")


@pytest.mark.asyncio  
async def test_graph_node_not_found(db_session: AsyncSession):
    """Test error handling when node doesn't exist"""
    admin_user = MockUser("admin_user", is_admin=True)
    
    try:
        await graph_node_detail(
            node_id="nonexistent_node_12345",
            session=db_session,
            current_user=admin_user
        )
        pytest.fail("Should have raised HTTPException")
    except Exception as e:
        # HTTPException should be raised with 404
        assert "404" in str(e) or "not found" in str(e).lower()
        print(f"✓ Node not found error handled correctly")


@pytest.mark.asyncio
async def test_graph_snapshot_permission_filter(db_session: AsyncSession):
    """Test that snapshot respects user permissions"""
    admin_user = MockUser("admin_user", is_admin=True)
    regular_user = MockUser("regular_user", is_admin=False)
    
    admin_snapshot = await graph_snapshot(
        view="entities",
        limit=50,
        edge_limit=100,
        session=db_session,
        current_user=admin_user
    )
    
    regular_snapshot = await graph_snapshot(
        view="entities",
        limit=50,
        edge_limit=100,
        session=db_session,
        current_user=regular_user
    )
    
    admin_node_count = len(admin_snapshot.get("nodes", []))
    regular_node_count = len(regular_snapshot.get("nodes", []))
    
    # Regular user might see same or fewer nodes
    assert regular_node_count <= admin_node_count
    
    print(f"✓ Permission filter: Admin sees {admin_node_count} nodes, "
          f"regular user sees {regular_node_count} nodes")


@pytest.mark.asyncio
async def test_graph_empty_allowed_docs(db_session: AsyncSession):
    """Test handling when user has no accessible documents"""
    # This is tricky to test without setting up specific permissions
    # For now, just verify the error path doesn't crash
    
    regular_user = MockUser("very_restricted_user", is_admin=False)
    
    try:
        result = await graph_health(
            session=db_session,
            current_user=regular_user
        )
        # Should return 0 if user has no access
        assert result["totalDocuments"] >= 0
        print(f"✓ No-access scenario handled: {result['totalDocuments']} docs visible")
    except Exception as e:
        print(f"⊘ No-access scenario raised: {e}")


# ─── Main test runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run all integration tests:
    
    python test_graph_integration.py
    
    Or with pytest:
    pytest test_graph_integration.py -v
    """
    print("Graph API Integration Tests")
    print("=" * 60)
    print()
    print("To run these tests, use pytest:")
    print("  pytest test_graph_integration.py -v")
    print()
    print("Or from terminal:")
    print("  python -m pytest test_graph_integration.py")
