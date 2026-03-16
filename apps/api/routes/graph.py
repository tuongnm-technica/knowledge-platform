from __future__ import annotations

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user, require_admin
from storage.db.db import get_db
from graph.graph_view import GraphViewBuilder


router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/health")
async def graph_health(
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    docs_by_source = (
        await session.execute(text("SELECT source, COUNT(*) AS c FROM documents GROUP BY source ORDER BY c DESC"))
    ).mappings().all()
    docs_by_source = [{"source": r["source"], "count": int(r["c"])} for r in docs_by_source]

    latest_by_source = (
        await session.execute(text("SELECT source, MAX(updated_at) AS latest FROM documents GROUP BY source"))
    ).mappings().all()
    latest_map = {r["source"]: r["latest"] for r in latest_by_source}

    entity_count = int((await session.execute(text("SELECT COUNT(*) FROM entities"))).scalar() or 0)
    relation_count = int((await session.execute(text("SELECT COUNT(*) FROM entity_relations"))).scalar() or 0)
    doc_link_count = int((await session.execute(text("SELECT COUNT(*) FROM document_links"))).scalar() or 0)
    explicit_link_count = int((await session.execute(text("SELECT COUNT(*) FROM document_links WHERE kind = 'explicit'"))).scalar() or 0)

    orphan_count = int(
        (await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM entities e
                LEFT JOIN entity_relations r1 ON r1.source_id = e.id
                LEFT JOIN entity_relations r2 ON r2.target_id = e.id
                WHERE r1.id IS NULL AND r2.id IS NULL
                """
            )
        )).scalar()
        or 0
    )

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
            stale_sources.append({"source": src, "days": age_days})

    missing_sources = [r["source"] for r in docs_by_source if int(r["count"]) == 0]

    return {
        "documents_by_source": docs_by_source,
        "stale_sources_30d": stale_sources,
        "missing_sources": missing_sources,
        "entities": entity_count,
        "relations": relation_count,
        "document_links": doc_link_count,
        "explicit_links": explicit_link_count,
        "orphan_entities": orphan_count,
    }


@router.get("/snapshot")
async def graph_snapshot(
    limit: int = 120,
    edge_limit: int = 240,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    limit = max(20, min(int(limit), 400))
    edge_limit = max(20, min(int(edge_limit), 1200))

    top = (
        await session.execute(
            text(
                """
                SELECT e.id::text AS id, e.name, COALESCE(e.entity_type, '') AS entity_type, COUNT(*) AS mentions
                FROM document_entities de
                JOIN entities e ON e.id = de.entity_id
                GROUP BY e.id, e.name, e.entity_type
                ORDER BY mentions DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    nodes = [
        {
            "id": r["id"],
            "label": r["name"],
            "type": r["entity_type"] or "entity",
            "mentions": int(r["mentions"] or 0),
        }
        for r in top
    ]
    ids = [n["id"] for n in nodes]
    if not ids:
        return {"nodes": [], "edges": []}

    edges = (
        await session.execute(
            text(
                """
                SELECT source_id::text AS source, target_id::text AS target, relation_type
                FROM entity_relations
                WHERE source_id::text = ANY(:ids) AND target_id::text = ANY(:ids)
                LIMIT :edge_limit
                """
            ),
            {"ids": ids, "edge_limit": edge_limit},
        )
    ).mappings().all()

    return {
        "nodes": nodes,
        "edges": [
            {"source": r["source"], "target": r["target"], "type": r.get("relation_type") or ""}
            for r in edges
        ],
    }


@router.get("/view")
async def graph_view(
    since_days: int = 30,
    per_source: int = 90,
    semantic_k: int = 3,
    semantic_min_weight: float = 3.0,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await GraphViewBuilder(session).build_overview(
        since_days=since_days,
        per_source=per_source,
        semantic_k=semantic_k,
        semantic_min_weight=semantic_min_weight,
    )


@router.get("/focus")
async def graph_focus(
    node_id: str,
    depth: int = 2,
    max_docs: int = 260,
    semantic_k: int = 4,
    semantic_min_weight: float = 3.0,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await GraphViewBuilder(session).build_focus(
        node_id=node_id,
        depth=depth,
        max_docs=max_docs,
        semantic_k=semantic_k,
        semantic_min_weight=semantic_min_weight,
    )


@router.get("/trace")
async def graph_trace(
    doc_id: str | None = None,
    jira_key: str | None = None,
    depth: int = 4,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await GraphViewBuilder(session).trace_root_cause(doc_id=doc_id, jira_key=jira_key, depth=depth)


@router.get("/impact")
async def graph_impact(
    doc_id: str,
    depth: int = 3,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await GraphViewBuilder(session).impact_analysis(doc_id=doc_id, depth=depth)


@router.get("/gaps")
async def graph_gaps(
    since_days: int = 30,
    per_source: int = 120,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    return await GraphViewBuilder(session).gap_insights(since_days=since_days, per_source=per_source)
