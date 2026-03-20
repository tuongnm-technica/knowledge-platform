from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from storage.db.db import get_db
from graph.graph_view import GraphViewBuilder
from permissions.filter import PermissionFilter

import structlog

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/health")
async def graph_health(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    GET /graph/health — Dashboard health metrics
    
    Returns health status: total documents, freshness, coverage, connector breakdown
    Filters by user permissions (admin sees all, users see only accessible docs)
    """
    try:
        # Get permission filter for the user
        perm_filter = PermissionFilter(session)
        allowed_docs = await perm_filter.allowed_docs(current_user.user_id)
        
        # Build query - admins see all, others see filtered
        params = {}
        base_query = "SELECT source, COUNT(*) AS c FROM documents"
        if allowed_docs is not None:
            # User is non-admin: filter by allowed documents
            if not allowed_docs:
                # User has no access
                return {
                    "totalDocuments": 0,
                    "lastUpdated": None,
                    "coveragePercent": 0,
                    "freshnessDays": 0,
                    "statusByConnector": {},
                    "staleSources": [],
                    "missingConnectors": [],
                }
            base_query += " WHERE id::text = ANY(:allowed)"
            params["allowed"] = list(allowed_docs)
        
        base_query += " GROUP BY source ORDER BY c DESC"
        
        docs_by_source = (
            await session.execute(text(base_query), params)
        ).mappings().all()
        docs_by_source = [{"source": r["source"], "count": int(r["c"])} for r in docs_by_source]

        latest_query = "SELECT source, MAX(updated_at) AS latest FROM documents"
        if allowed_docs is not None and allowed_docs:
            latest_query += " WHERE id::text = ANY(:allowed)"
        latest_query += " GROUP BY source"
        
        latest_by_source = (
            await session.execute(text(latest_query), params)
        ).mappings().all()
        latest_map = {r["source"]: r["latest"] for r in latest_by_source}

        total_docs = sum(r["count"] for r in docs_by_source)
        now = datetime.now(timezone.utc)
        
        stale_sources = []
        for row in docs_by_source:
            src = row["source"]
            latest = latest_map.get(src)
            if latest is None:
                continue
            try:
                age_days = int((now - latest.replace(tzinfo=timezone.utc)).total_seconds() / 86400)
            except Exception:
                continue
            if age_days >= 30:
                stale_sources.append({"connector": src, "daysSinceSync": age_days, "documentCount": row["count"], "priority": "high" if age_days > 60 else "medium"})

        missing_connectors = [r["source"] for r in docs_by_source if int(r["count"]) == 0]
        
        # Calculate coverage percent
        total_sources = len(docs_by_source)
        covered_sources = sum(1 for r in docs_by_source if r["count"] > 0)
        coverage_percent = (covered_sources / total_sources * 100) if total_sources > 0 else 0

        # Get freshness (days since most recent update)
        freshness_days = 0
        if latest_map:
            most_recent = max(latest_map.values())
            try:
                freshness_days = int((now - most_recent.replace(tzinfo=timezone.utc)).total_seconds() / 86400)
            except Exception:
                pass

        # Calculate graph stats
        entities_count = 0
        relations_count = 0
        doc_links_count = 0
        
        if allowed_docs is not None and not allowed_docs:
            pass
        else:
            try:
                entities_count = await session.scalar(text("SELECT count(*) FROM entities"))
                relations_count = await session.scalar(text("SELECT count(*) FROM entity_relations"))
                doc_links_count = await session.scalar(text("SELECT count(*) FROM document_links"))
            except Exception:
                pass

        return {
            "totalDocuments": total_docs,
            "lastUpdated": max(latest_map.values()).isoformat() if latest_map else None,
            "coveragePercent": round(coverage_percent, 1),
            "freshnessDays": freshness_days,
            "statusByConnector": {
                r["source"]: {
                    "documentCount": r["count"],
                    "lastSync": latest_map.get(r["source"], datetime.now(timezone.utc)).isoformat(),
                    "status": "ok" if r["count"] > 0 and r["source"] not in [s["connector"] for s in stale_sources] else ("warning" if r["count"] > 0 else "error")
                }
                for r in docs_by_source
            },
            "staleSources": stale_sources,
            "missingConnectors": missing_connectors,
            "entities": entities_count or 0,
            "relations": relations_count or 0,
            "document_links": doc_links_count or 0,
        }
    except Exception as e:
        log.exception("graph.health.error", user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch health metrics")


@router.get("/snapshot")
async def graph_snapshot(
    view: str = "entities",
    limit: int = 120,
    edge_limit: int = 240,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    GET /graph/snapshot — Interactive graph data (nodes + edges)
    
    Params:
      - view: Graph view type (entities, documents, users)
      - limit: Max nodes to return (20-400)
      - edge_limit: Max edges to return (20-1200)
    """
    try:
        limit = max(20, min(int(limit), 400))
        edge_limit = max(20, min(int(edge_limit), 1200))

        # Apply user permission filter
        perm_filter = PermissionFilter(session)
        allowed_docs = await perm_filter.allowed_docs(current_user.user_id)
        
        if allowed_docs is not None and not allowed_docs:
            # User has no access
            return {"nodes": [], "edges": []}

        # Build query with optional permission filter
        entity_query = """
            SELECT e.id::text AS id, e.name, COALESCE(e.entity_type, '') AS entity_type, COUNT(*) AS mentions
            FROM document_entities de
            JOIN entities e ON e.id = de.entity_id
        """
        
        params = {"limit": limit}
        
        if allowed_docs is not None:
            entity_query += " WHERE de.document_id::text = ANY(:allowed)"
            params["allowed"] = list(allowed_docs)
        
        entity_query += """
            GROUP BY e.id, e.name, e.entity_type
            ORDER BY mentions DESC
            LIMIT :limit
        """

        top = (
            await session.execute(text(entity_query), params)
        ).mappings().all()

        nodes = [
            {
                "id": r["id"],
                "label": r["name"],
                "type": r["entity_type"] or "entity",
                "size": min(12, 4 + int(r["mentions"] or 0) / 2),
                "color": "#4a90e2",
            }
            for r in top
        ]
        ids = [n["id"] for n in nodes]
        if not ids:
            return {"nodes": [], "edges": []}

        edges_query = """
            SELECT source_id::text AS source, target_id::text AS target, relation_type
            FROM entity_relations
            WHERE source_id::text = ANY(:ids) AND target_id::text = ANY(:ids)
            LIMIT :edge_limit
        """

        edges_result = (
            await session.execute(
                text(edges_query),
                {"ids": list(ids), "edge_limit": edge_limit}
            )
        ).mappings().all()

        return {
            "nodes": nodes,
            "edges": [
                {
                    "from": r["source"],
                    "to": r["target"],
                    "label": r.get("relation_type") or "related",
                }
                for r in edges_result
            ],
        }
    except Exception as e:
        log.exception("graph.snapshot.error", user_id=current_user.user_id, view=view, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch graph snapshot")


@router.get("/view")
async def graph_view(
    since_days: int = 30,
    per_source: int = 90,
    semantic_k: int = 3,
    semantic_min_weight: float = 3.0,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """GET /graph/view — Overview of all sources and connections"""
    try:
        builder = GraphViewBuilder(session)
        return await builder.build_overview(
            since_days=since_days,
            per_source=per_source,
            semantic_k=semantic_k,
            semantic_min_weight=semantic_min_weight,
        )
    except Exception as e:
        log.exception("graph.view.error", user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to build view")


@router.get("/focus")
async def graph_focus(
    node_id: str,
    depth: int = 2,
    max_docs: int = 260,
    semantic_k: int = 4,
    semantic_min_weight: float = 3.0,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """GET /graph/focus — Focus on a specific node and its neighbors"""
    try:
        if not node_id or not node_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_id is required")
        
        builder = GraphViewBuilder(session)
        return await builder.build_focus(
            node_id=node_id,
            depth=depth,
            max_docs=max_docs,
            semantic_k=semantic_k,
            semantic_min_weight=semantic_min_weight,
        )
    except Exception as e:
        log.exception("graph.focus.error", user_id=current_user.user_id, node_id=node_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to build focus view")


@router.get("/trace")
async def graph_trace(
    doc_id: str | None = None,
    jira_key: str | None = None,
    depth: int = 4,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """GET /graph/trace — Trace document dependencies and root causes"""
    try:
        if not doc_id and not jira_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id or jira_key is required")
        
        builder = GraphViewBuilder(session)
        return await builder.trace_root_cause(doc_id=doc_id, jira_key=jira_key, depth=depth)
    except Exception as e:
        log.exception("graph.trace.error", user_id=current_user.user_id, doc_id=doc_id, jira_key=jira_key, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to trace dependencies")


@router.get("/impact")
async def graph_impact(
    doc_id: str,
    depth: int = 3,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """GET /graph/impact — Impact analysis of document changes"""
    try:
        if not doc_id or not doc_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id is required")
        
        builder = GraphViewBuilder(session)
        return await builder.impact_analysis(doc_id=doc_id, depth=depth)
    except Exception as e:
        log.exception("graph.impact.error", user_id=current_user.user_id, doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze impact")


@router.get("/gaps")
async def graph_gaps(
    since_days: int = 30,
    per_source: int = 120,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """GET /graph/gaps — Gap insights and recommendations"""
    try:
        builder = GraphViewBuilder(session)
        gaps = await builder.gap_insights(since_days=since_days, per_source=per_source)
        
        return {
            "staleSources": gaps.get("staleSources", []),
            "orphanEntities": gaps.get("orphanEntities", []),
            "missingRelationships": gaps.get("missingRelationships", []),
            "isolatedDocuments": gaps.get("isolatedDocuments", []),
        }
    except Exception as e:
        log.exception("graph.gaps.error", user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch gaps")


@router.get("/node/{node_id}")
async def graph_node_detail(
    node_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    GET /graph/node/{nodeId} — Get detailed information about a single node
    
    Returns: Node metadata, type, relationships, and related documents
    """
    try:
        if not node_id or not node_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="node_id is required")
        
        # Apply user permission filter
        perm_filter = PermissionFilter(session)
        allowed_docs = await perm_filter.allowed_docs(current_user.user_id)
        
        # Check if node is an entity or document
        entity_result = await session.execute(
            text("SELECT id::text, name AS label, entity_type AS type FROM entities WHERE id::text = :node_id"),
            {"node_id": node_id}
        )
        entity_row = entity_result.mappings().first()
        
        if entity_row:
            # Node is an entity
            # Get mention count
            mention_query = "SELECT COUNT(*) AS mentions FROM document_entities WHERE entity_id::text = :node_id"
            params = {"node_id": node_id}
            
            if allowed_docs is not None:
                mention_query += " AND document_id::text = ANY(:allowed)"
                params["allowed"] = list(allowed_docs)
            
            mention_result = await session.execute(
                text(mention_query),
                params
            )
            mentions = mention_result.scalar() or 0
            
            # Get related entities
            relation_query = """
                SELECT source_id::text, target_id::text, relation_type
                FROM entity_relations
                WHERE (source_id::text = :node_id OR target_id::text = :node_id)
                LIMIT 20
            """
            
            relations_result = await session.execute(
                text(relation_query),
                {"node_id": node_id}
            )
            related = [
                {
                    "from": r["source_id"],
                    "to": r["target_id"],
                    "type": r["relation_type"],
                }
                for r in relations_result.mappings().all()
            ]
            
            return {
                "id": entity_row["id"],
                "label": entity_row["label"],
                "type": entity_row["type"] or "entity",
                "metadata": {
                    "mentions": int(mentions),
                    "relatedEntities": len(related),
                },
                "related": related,
            }
        else:
            # Check if node is a document
            doc_query = "SELECT id::text, title, source, updated_at FROM documents WHERE id::text = :node_id"
            
            if allowed_docs is not None:
                if node_id not in allowed_docs:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this document")
            
            doc_result = await session.execute(
                text(doc_query),
                {"node_id": node_id}
            )
            doc_row = doc_result.mappings().first()
            
            if not doc_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
            
            # Get related documents
            related_docs_query = """
                SELECT DISTINCT d.id::text, d.title, COUNT(*) AS connection_strength
                FROM document_links dl
                JOIN documents d ON (d.id::text = dl.target_id::text OR d.id::text = dl.source_id::text)
                WHERE (dl.source_id::text = :doc_id OR dl.target_id::text = :doc_id)
                  AND d.id::text != :doc_id
                GROUP BY d.id, d.title
                ORDER BY connection_strength DESC
                LIMIT 10
            """
            
            related_result = await session.execute(
                text(related_docs_query),
                {"doc_id": node_id}
            )
            related_docs = [
                {
                    "id": r["id"],
                    "label": r["title"],
                    "strength": int(r["connection_strength"] or 0),
                }
                for r in related_result.mappings().all()
            ]
            
            return {
                "id": doc_row["id"],
                "label": doc_row["title"],
                "type": "document",
                "metadata": {
                    "source": doc_row["source"],
                    "updated": doc_row["updated_at"].isoformat() if doc_row["updated_at"] else None,
                    "relatedCount": len(related_docs),
                },
                "related": related_docs,
            }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("graph.node_detail.error", user_id=current_user.user_id, node_id=node_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch node details")
