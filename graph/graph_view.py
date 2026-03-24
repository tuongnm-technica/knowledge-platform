from __future__ import annotations

import json
import heapq
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graph.document_linker import DocumentLinker


def _jsonish(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value) if value else {}
        except Exception:
            return {}
    return {}


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _iso_date(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_person(value: str) -> str:
    v = _safe_str(value).lower().lstrip("@")
    v = re.sub(r"\s+", " ", v)
    return v


@dataclass(frozen=True)
class DocRow:
    id: str
    source: str
    title: str
    url: str
    author: str
    updated_at: datetime | None
    metadata: dict


class GraphPalette:
    JIRA = "#1D4ED8"
    CONFLUENCE = "#16A34A"
    SLACK = "#7C3AED"
    FILE = "#F97316"
    USER = "#64748B"
    SUPER = "#0F766E"
    CHUNK = "#8B5CF6"
    ENTITY = "#EC4899"
    ISSUE = "#EF4444"
    SERVICE = "#10B981"


class GraphViewBuilder:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._linker = DocumentLinker(session)

    async def build_overview(
        self,
        *,
        since_days: int = 30,
        per_source: int = 90,
        semantic_k: int = 3,
        semantic_min_weight: float = 3.0,
        include_sources: list[str] | None = None,
        max_detail_docs: int = 520,
    ) -> dict:
        include_sources = include_sources or ["jira", "confluence", "slack", "file_server"]
        docs = await self._fetch_recent_docs(
            since_days=max(1, min(int(since_days), 365)),
            per_source=max(20, min(int(per_source), 250)),
            include_sources=include_sources,
        )
        docs = docs[: max(120, min(int(max_detail_docs), 1200))]

        detail = await self._build_detail_graph(
            docs,
            semantic_k=max(0, min(int(semantic_k), 12)),
            semantic_min_weight=max(1.0, float(semantic_min_weight)),
        )
        super_graph = self._build_super_graph(detail)
        return {
            "version": 2,
            "generated_at": _now_utc().isoformat(),
            "params": {
                "since_days": since_days,
                "per_source": per_source,
                "semantic_k": semantic_k,
                "semantic_min_weight": semantic_min_weight,
                "include_sources": include_sources,
            },
            "detail": detail,
            "super": super_graph,
            "insights": self._gap_insights(detail),
        }

    async def build_focus(
        self,
        *,
        node_id: str,
        depth: int = 2,
        max_docs: int = 260,
        semantic_k: int = 4,
        semantic_min_weight: float = 3.0,
        include_chunks: bool = True,
    ) -> dict:
        node_id = _safe_str(node_id)
        depth = max(1, min(int(depth), 5))
        max_docs = max(60, min(int(max_docs), 900))
        semantic_k = max(0, min(int(semantic_k), 12))
        semantic_min_weight = max(1.0, float(semantic_min_weight))

        if node_id.startswith("user:"):
            doc_ids = await self._docs_for_user_entity(node_id.split(":", 1)[1], limit=max_docs)
        elif node_id.startswith("doc:"):
            doc_ids = [node_id.split(":", 1)[1]]
        elif node_id.startswith("chunk:"):
            # Focus on a chunk: get its document and neighbors
            doc_ids = await self._doc_id_for_chunk(node_id.split(":", 1)[1])
        else:
            doc_ids = await self._docs_for_super_node(node_id, limit=max_docs)

        docs = await self._fetch_docs_by_ids(doc_ids)
        detail = await self._build_detail_graph(
            docs,
            semantic_k=semantic_k,
            semantic_min_weight=semantic_min_weight,
            bfs_root_nodes=[node_id] if node_id else None,
            depth=depth,
            include_chunks=include_chunks,
        )
        return {"detail": detail, "super": self._build_super_graph(detail), "insights": self._gap_insights(detail)}

    async def build_query_subgraph(
        self,
        *,
        query: str,
        limit: int = 15,
        depth: int = 2,
    ) -> dict:
        from indexing.vector_index import VectorIndex

        query = _safe_str(query)
        if not query:
            return {"error": "Query is empty"}

        vindex = VectorIndex(self._session)
        # Find top-k chunks
        hits = await vindex.search(query, limit=limit)
        if not hits:
            return {"nodes": [], "edges": [], "info": "No relevant chunks found"}

        chunk_ids = [h["chunk_id"] for h in hits]
        doc_ids = list(set(h["document_id"] for h in hits))
        
        docs = await self._fetch_docs_by_ids(doc_ids)
        detail = await self._build_detail_graph(
            docs,
            semantic_k=3,
            semantic_min_weight=2.0,
            bfs_root_nodes=[f"chunk:{cid}" for cid in chunk_ids],
            depth=depth,
            include_chunks=True,
            limit_chunks=chunk_ids, # Only show found chunks or neighbors
        )
        
        # Highlight entry nodes
        highlight = {f"chunk:{cid}": True for cid in chunk_ids}
        for n in detail.get("nodes") or []:
            if n["id"] in highlight:
                n["highlight"] = True
                n["size"] = n.get("size", 11) * 1.5

        return {
            "detail": detail,
            "super": self._build_super_graph(detail),
            "insights": self._gap_insights(detail)
        }

    async def traverse_graph(
        self,
        *,
        node_id: str,
        limit: int = 15,
        relation_kind: str | None = None,
    ) -> dict:
        """Helper for LLM reasoning to explore neighbors."""
        detail = await self.build_focus(node_id=node_id, depth=1, include_chunks=True)
        nodes = detail.get("detail", {}).get("nodes", [])
        edges = detail.get("detail", {}).get("edges", [])
        
        if relation_kind:
            edges = [e for e in edges if e.get("kind") == relation_kind]
            node_ids = {e.get("source") for e in edges} | {e.get("target") for e in edges}
            nodes = [n for n in nodes if n.get("id") in node_ids]
            
        nodes_out = list(nodes)[:limit]
        edges_out = list(edges)[:limit]
            
        return {"nodes": nodes_out, "edges": edges_out}

    async def trace_root_cause(
        self,
        *,
        doc_id: str | None = None,
        jira_key: str | None = None,
        depth: int = 4,
    ) -> dict:
        start_doc_id = _safe_str(doc_id)
        if not start_doc_id and jira_key:
            start_doc_id = await self._jira_doc_id_for_key(_safe_str(jira_key).upper()) or ""
        if not start_doc_id:
            return {"error": "Start node not found"}

        docs = await self._fetch_recent_docs(
            since_days=120,
            per_source=140,
            include_sources=["jira", "confluence", "slack", "file_server"],
            always_include_doc_ids=[start_doc_id],
        )
        depth_c = max(1, min(int(depth), 6))
        root = f"doc:{start_doc_id}"
        detail = await self._build_detail_graph(
            docs,
            semantic_k=5,
            semantic_min_weight=3.0,
            bfs_root_nodes=[root],
            depth=depth_c,
        )
        highlight = self._bfs_highlight(detail, root=root, depth=depth_c)
        return {
            **highlight,
            "detail": detail,
            "super": self._build_super_graph(detail),
            "insights": self._gap_insights(detail),
        }

    async def impact_analysis(self, *, doc_id: str, depth: int = 3) -> dict:
        start_doc_id = _safe_str(doc_id)
        if not start_doc_id:
            return {"error": "Missing doc_id"}
        docs = await self._fetch_recent_docs(
            since_days=180,
            per_source=160,
            include_sources=["jira", "confluence", "slack", "file_server"],
            always_include_doc_ids=[start_doc_id],
        )
        depth_c = max(1, min(int(depth), 6))
        root = f"doc:{start_doc_id}"
        detail = await self._build_detail_graph(
            docs,
            semantic_k=4,
            semantic_min_weight=3.0,
            bfs_root_nodes=[root],
            depth=depth_c,
        )
        highlight = self._bfs_highlight(detail, root=root, depth=depth_c)
        node_by_id = {n["id"]: n for n in (detail.get("nodes") or [])}
        impacted = []
        for nid in highlight.get("highlight_nodes") or []:
            n = node_by_id.get(nid)
            if n and n.get("source") in {"jira", "confluence"}:
                impacted.append(n)
        return {
            **highlight,
            "impacted": impacted[:80],
            "detail": detail,
            "super": self._build_super_graph(detail),
            "insights": self._gap_insights(detail),
        }

    async def gap_insights(self, *, since_days: int = 30, per_source: int = 120) -> dict:
        docs = await self._fetch_recent_docs(
            since_days=max(1, min(int(since_days), 365)),
            per_source=max(40, min(int(per_source), 250)),
            include_sources=["jira", "confluence", "slack", "file_server"],
        )
        detail = await self._build_detail_graph(docs, semantic_k=4, semantic_min_weight=3.0)
        return {"generated_at": _now_utc().isoformat(), "insights": self._gap_insights(detail)}

    async def _fetch_recent_docs(
        self,
        *,
        since_days: int,
        per_source: int,
        include_sources: list[str],
        always_include_doc_ids: list[str] | None = None,
    ) -> list[DocRow]:
        since = _now_utc() - timedelta(days=int(since_days))
        docs: list[DocRow] = []
        seen: set[str] = set()

        for src in include_sources:
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text AS id, source, title, url, author, updated_at, metadata
                        FROM documents
                        WHERE source = :src
                          AND updated_at >= :since
                        ORDER BY updated_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"src": src, "since": since.replace(tzinfo=None), "limit": int(per_source)},
                )
            ).mappings().all()
            for r in rows:
                doc_id = str(r.get("id") or "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                docs.append(
                    DocRow(
                        id=doc_id,
                        source=str(r.get("source") or ""),
                        title=str(r.get("title") or ""),
                        url=str(r.get("url") or ""),
                        author=str(r.get("author") or ""),
                        updated_at=r.get("updated_at"),
                        metadata=_jsonish(r.get("metadata")),
                    )
                )

        for doc_id in (always_include_doc_ids or []):
            doc_id = _safe_str(doc_id)
            if not doc_id or doc_id in seen:
                continue
            row = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text AS id, source, title, url, author, updated_at, metadata
                        FROM documents
                        WHERE id::text = :id
                        LIMIT 1
                        """
                    ),
                    {"id": doc_id},
                )
            ).mappings().first()
            if not row:
                continue
            seen.add(doc_id)
            docs.append(
                DocRow(
                    id=str(row.get("id") or ""),
                    source=str(row.get("source") or ""),
                    title=str(row.get("title") or ""),
                    url=str(row.get("url") or ""),
                    author=str(row.get("author") or ""),
                    updated_at=row.get("updated_at"),
                    metadata=_jsonish(row.get("metadata")),
                )
            )

        docs.sort(key=lambda d: d.updated_at or datetime.min, reverse=True)
        return docs

    async def _fetch_docs_by_ids(self, doc_ids: Iterable[str]) -> list[DocRow]:
        ids = [str(x) for x in (doc_ids or []) if str(x).strip()]
        if not ids:
            return []
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT id::text AS id, source, title, url, author, updated_at, metadata
                    FROM documents
                    WHERE id::text = ANY(:ids)
                    """
                ),
                {"ids": ids},
            )
        ).mappings().all()
        out: list[DocRow] = []
        for r in rows:
            out.append(
                DocRow(
                    id=str(r.get("id") or ""),
                    source=str(r.get("source") or ""),
                    title=str(r.get("title") or ""),
                    url=str(r.get("url") or ""),
                    author=str(r.get("author") or ""),
                    updated_at=r.get("updated_at"),
                    metadata=_jsonish(r.get("metadata")),
                )
            )
        return out

    async def _doc_id_for_chunk(self, chunk_id: str) -> list[str]:
        chunk_id = _safe_str(chunk_id)
        if not chunk_id:
            return []
        result = await self._session.execute(
            text("SELECT document_id::text FROM chunks WHERE id = :id LIMIT 1"),
            {"id": chunk_id},
        )
        row = result.scalar()
        return [str(row)] if row else []

    async def _jira_doc_id_for_key(self, jira_key: str) -> str | None:
        jira_key = _safe_str(jira_key).upper()
        if not jira_key:
            return None
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT id::text AS id
                    FROM documents
                    WHERE source = 'jira'
                      AND (metadata->>'issue_key') = :key
                    LIMIT 1
                    """
                ),
                {"key": jira_key},
            )
        ).scalar()
        return str(row) if row else None

    async def _docs_for_user_entity(self, entity_id: str, *, limit: int) -> list[str]:
        entity_id = _safe_str(entity_id)
        if not entity_id:
            return []
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT de.document_id::text AS id
                    FROM document_entities de
                    WHERE de.entity_id::text = :eid
                      AND de.entity_type = 'person'
                    LIMIT :limit
                    """
                ),
                {"eid": entity_id, "limit": int(limit)},
            )
        ).scalars().all()
        return [str(r) for r in rows if r]

    async def _docs_for_super_node(self, node_id: str, *, limit: int) -> list[str]:
        node_id = _safe_str(node_id)
        if node_id.startswith("slack_channel:"):
            cid = node_id.split(":", 1)[1]
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text
                        FROM documents
                        WHERE source='slack'
                          AND (metadata->>'channel_id') = :cid
                        ORDER BY updated_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"cid": cid, "limit": int(limit)},
                )
            ).scalars().all()
            return [str(r) for r in rows if r]
        if node_id.startswith("confluence_space:"):
            sk = node_id.split(":", 1)[1]
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text
                        FROM documents
                        WHERE source='confluence'
                          AND (metadata->>'space_key') = :sk
                        ORDER BY updated_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"sk": sk, "limit": int(limit)},
                )
            ).scalars().all()
            return [str(r) for r in rows if r]
        if node_id.startswith("file_folder:"):
            folder = node_id.split(":", 1)[1]
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text
                        FROM documents
                        WHERE source='file_server'
                          AND (metadata->>'top_folder') = :f
                        ORDER BY updated_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"f": folder, "limit": int(limit)},
                )
            ).scalars().all()
            return [str(r) for r in rows if r]
        return []

    async def _build_detail_graph(
        self,
        docs: list[DocRow],
        *,
        semantic_k: int,
        semantic_min_weight: float,
        bfs_root_nodes: list[str] | None = None,
        depth: int | None = None,
        include_chunks: bool = False,
        limit_chunks: list[str] | None = None,
    ) -> dict:
        nodes: list[dict] = []
        edges: list[dict] = []
        node_by_id: dict[str, dict] = {}

        doc_rows: dict[str, DocRow] = {d.id: d for d in docs if d and d.id}
        doc_ids = sorted(doc_rows.keys())

        for doc in docs:
            if not doc.id:
                continue
            node = self._doc_node(doc)
            nodes.append(node)
            node_by_id[node["id"]] = node

        # Parent container nodes: Slack channel / Confluence space / File folder.
        for doc in docs:
            parent = self._parent_node_for_doc(doc)
            if not parent:
                continue
            if parent["id"] not in node_by_id:
                nodes.append(parent)
                node_by_id[parent["id"]] = parent
            edges.append(self._edge(parent["id"], f"doc:{doc.id}", kind="membership", relation="contains", weight=1.0))

        # User nodes (IdentityResolver -> KnowledgeGraph -> document_entities(entity_type='person')).
        user_links = await self._fetch_doc_person_entities(doc_ids)
        for doc_id, persons in user_links.items():
            doc = doc_rows.get(doc_id)
            if not doc:
                continue
            role_map = self._roles_for_doc(doc)
            for person in persons:
                user_node_id = f"user:{person['id']}"
                if user_node_id not in node_by_id:
                    user_node = {
                        "id": user_node_id,
                        "kind": "user",
                        "subkind": "user",
                        "label": person["name"],
                        "color": GraphPalette.USER,
                        "icon": "user",
                        "url": "",
                        "meta": {},
                    }
                    nodes.append(user_node)
                    node_by_id[user_node_id] = user_node

                roles = role_map.get(_normalize_person(person["name"]), [])
                edges.append(
                    self._edge(
                        user_node_id,
                        f"doc:{doc_id}",
                        kind="actor",
                        relation="involved",
                        weight=float(1.0 + 0.25 * len(roles)),
                        meta={"roles": roles},
                    )
                )

        # Entity nodes (API, Issue, Service, etc.)
        entity_links = await self._fetch_doc_entities(doc_ids)
        all_entity_ids = set()
        for ents in entity_links.values():
            for e in ents:
                all_entity_ids.add(e["id"])
        
        entity_meta = await self._fetch_entity_details(list(all_entity_ids))
        for doc_id, entities in entity_links.items():
            for ent in entities:
                ent_id = ent["id"]
                ent_type = ent["type"]
                meta = entity_meta.get(ent_id) or {}
                ent_node_id = f"entity:{ent_id}"
                
                if ent_node_id not in node_by_id:
                    color = GraphPalette.ENTITY
                    icon = "circle"
                    if ent_type == "jira_issue":
                        color = GraphPalette.ISSUE
                        icon = "bug"
                    elif ent_type == "service":
                        color = GraphPalette.SERVICE
                        icon = "server"
                    elif ent_type == "project":
                        color = GraphPalette.SUPER
                        icon = "briefcase"
                    
                    node = {
                        "id": ent_node_id,
                        "kind": "entity",
                        "subkind": ent_type,
                        "label": meta.get("name") or ent_id,
                        "color": color,
                        "icon": icon,
                        "meta": meta,
                    }
                    nodes.append(node)
                    node_by_id[ent_node_id] = node
                
                edges.append(
                    self._edge(
                        f"doc:{doc_id}",
                        ent_node_id,
                        kind="extraction",
                        relation="mentions",
                        weight=1.0,
                    )
                )

        # Chunk nodes
        if include_chunks:
            chunks_by_doc = await self._fetch_chunks_for_docs(doc_ids, limit_chunks=limit_chunks)
            for doc_id, doc_chunks in chunks_by_doc.items():
                for chunk in doc_chunks:
                    chunk_node_id = f"chunk:{chunk['id']}"
                    if chunk_node_id not in node_by_id:
                        node = {
                            "id": chunk_node_id,
                            "kind": "chunk",
                            "subkind": "chunk",
                            "label": f"Chunk {chunk['chunk_index']}",
                            "color": GraphPalette.CHUNK,
                            "icon": "align-left",
                            "meta": {"index": chunk["chunk_index"], "snippet": chunk["content"][:200]},
                        }
                        nodes.append(node)
                        node_by_id[chunk_node_id] = node
                    
                    edges.append(
                        self._edge(
                            f"doc:{doc_id}",
                            chunk_node_id,
                            kind="membership",
                            relation="contains",
                            weight=1.5,
                        )
                    )
                    
                    # Link Chunk to Entities mentioned in it (if text contains entity name)
                    doc_ents = entity_links.get(doc_id, [])
                    for ent in doc_ents:
                        ent_meta = entity_meta.get(ent["id"])
                        if ent_meta and ent_meta.get("name") and ent_meta["name"].lower() in chunk["content"].lower():
                            edges.append(
                                self._edge(
                                    chunk_node_id,
                                    f"entity:{ent['id']}",
                                    kind="textual",
                                    relation="mentions",
                                    weight=1.2,
                                )
                            )

        # Explicit doc-doc links (persisted at ingestion).
        edges.extend(await self._fetch_explicit_doc_links(doc_ids))

        # Implicit/Semantic links via entity overlap (cross-source only).
        if semantic_k > 0:
            entities_by_doc = await self._fetch_doc_entities(doc_ids)
            edges.extend(
                self._semantic_edges(
                    docs,
                    entities_by_doc,
                    k=int(semantic_k),
                    min_weight=float(semantic_min_weight),
                )
            )

        # Focus mode: crop subgraph around a root node (doc/user/container).
        if bfs_root_nodes and depth:
            cropped = self._crop_by_bfs(nodes, edges, roots=bfs_root_nodes, depth=int(depth))
            nodes, edges = cropped["nodes"], cropped["edges"]
            node_by_id = {n["id"]: n for n in nodes}

        edges = [e for e in edges if e.get("source") in node_by_id and e.get("target") in node_by_id]
        for n in nodes:
            n["size"] = self._node_size(n)
        return {"nodes": nodes, "edges": edges}

    async def _fetch_doc_person_entities(self, doc_ids: list[str]) -> dict[str, list[dict]]:
        if not doc_ids:
            return {}
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT
                      de.document_id::text AS document_id,
                      e.id::text AS entity_id,
                      e.name AS name
                    FROM document_entities de
                    JOIN entities e ON e.id = de.entity_id
                    WHERE de.document_id::text = ANY(:ids)
                      AND de.entity_type = 'person'
                    """
                ),
                {"ids": doc_ids},
            )
        ).mappings().all()
        out: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            out[str(r["document_id"])].append({"id": str(r["entity_id"]), "name": str(r.get("name") or "Unknown")})
        return out

    async def _fetch_doc_entities(self, doc_ids: list[str]) -> dict[str, list[dict]]:
        if not doc_ids:
            return {}
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT
                      de.document_id::text AS document_id,
                      e.id::text AS entity_id,
                      e.entity_type AS entity_type
                    FROM document_entities de
                    JOIN entities e ON e.id = de.entity_id
                    WHERE de.document_id::text = ANY(:ids)
                      AND de.entity_type != 'person'
                    """
                ),
                {"ids": doc_ids},
            )
        ).mappings().all()
        out: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            out[str(r["document_id"])].append({"id": str(r["entity_id"]), "type": str(r.get("entity_type") or "")})
        return out

    async def _fetch_entity_details(self, entity_ids: list[str]) -> dict[str, dict]:
        if not entity_ids:
            return {}
        rows = (
            await self._session.execute(
                text("SELECT id::text, name, entity_type, normalized_name FROM entities WHERE id::text = ANY(:ids)"),
                {"ids": entity_ids},
            )
        ).mappings().all()
        return {str(r["id"]): dict(r) for r in rows}

    async def _fetch_chunks_for_docs(self, doc_ids: list[str], limit_chunks: list[str] | None = None) -> dict[str, list[dict]]:
        if not doc_ids:
            return {}
        
        query = "SELECT id::text, document_id::text, content, chunk_index FROM chunks WHERE document_id::text = ANY(:doc_ids)"
        params = {"doc_ids": doc_ids}
        
        if limit_chunks:
            query += " AND id::text = ANY(:chunk_ids)"
            params["chunk_ids"] = limit_chunks
            
        rows = (await self._session.execute(text(query), params)).mappings().all()
        out: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            out[str(r["document_id"])].append(dict(r))
        return out

    async def _fetch_explicit_doc_links(self, doc_ids: list[str]) -> list[dict]:
        if not doc_ids:
            return []
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT source_document_id::text AS src, target_document_id::text AS dst, weight
                    FROM document_links
                    WHERE source_document_id::text = ANY(:ids)
                      AND target_document_id::text = ANY(:ids)
                      AND kind = 'explicit'
                    """
                ),
                {"ids": doc_ids},
            )
        ).mappings().all()

        out: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            a = f"doc:{r['src']}"
            b = f"doc:{r['dst']}"
            if (a, b) in seen:
                continue
            seen.add((a, b))
            out.append(self._edge(a, b, kind="explicit", relation="references", weight=float(r.get("weight") or 1.0)))
        return out

    def _semantic_edges(
        self,
        docs: list[DocRow],
        entities_by_doc: dict[str, list[dict]],
        *,
        k: int,
        min_weight: float,
    ) -> list[dict]:
        type_weight = {"jira_issue": 4.0, "project": 3.0, "service": 2.0, "channel": 1.0, "email": 1.0}
        doc_source = {d.id: d.source for d in docs}

        inv: dict[str, list[str]] = defaultdict(list)
        ent_type: dict[str, str] = {}
        for doc_id, ents in (entities_by_doc or {}).items():
            for e in ents or []:
                eid = _safe_str(e.get("id"))
                if not eid:
                    continue
                inv[eid].append(doc_id)
                ent_type[eid] = _safe_str(e.get("type"))

        out: list[dict] = []
        seen: set[tuple[str, str]] = set()

        for doc in docs:
            scores: dict[str, float] = defaultdict(float)
            for e in entities_by_doc.get(doc.id, []):
                eid = _safe_str(e.get("id"))
                if not eid:
                    continue
                w = type_weight.get(ent_type.get(eid, ""), 1.0)
                for other in inv.get(eid, []):
                    if other == doc.id:
                        continue
                    if doc_source.get(other) == doc.source:
                        continue
                    scores[other] += w

            if not scores:
                continue

            for other_id, weight in heapq.nlargest(max(0, int(k)), scores.items(), key=lambda it: it[1]):
                if float(weight) < float(min_weight):
                    continue
                a = f"doc:{doc.id}"
                b = f"doc:{other_id}"
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                out.append(self._edge(key[0], key[1], kind="semantic", relation="similar_to", weight=float(weight)))

        return out

    def _build_super_graph(self, detail: dict) -> dict:
        nodes = detail.get("nodes") or []
        edges = detail.get("edges") or []
        doc_nodes = [n for n in nodes if str(n.get("id", "")).startswith("doc:")]

        cluster_key: dict[str, str] = {}
        members: dict[str, list[str]] = defaultdict(list)
        for n in doc_nodes:
            meta = _jsonish(n.get("meta"))
            topic = _safe_str(meta.get("topic_key")) or self._fallback_topic(n)
            cid = f"cluster:{topic}"
            cluster_key[n["id"]] = cid
            members[cid].append(n["id"])

        super_nodes = []
        for cid, mids in members.items():
            super_nodes.append(
                {
                    "id": cid,
                    "kind": "super",
                    "subkind": "cluster",
                    "label": cid.split(":", 1)[1],
                    "color": GraphPalette.SUPER,
                    "icon": "cluster",
                    "size": 10 + math.log2(1 + len(mids)) * 6,
                    "meta": {"members": len(mids)},
                }
            )

        super_edges_map: dict[tuple[str, str, str], dict] = {}
        for e in edges:
            a = _safe_str(e.get("source"))
            b = _safe_str(e.get("target"))
            if a not in cluster_key or b not in cluster_key:
                continue
            ca = cluster_key[a]
            cb = cluster_key[b]
            if ca == cb:
                continue
            x, y = (ca, cb) if ca < cb else (cb, ca)
            kind = _safe_str(e.get("kind")) or "derived"
            key = (x, y, kind)
            agg = super_edges_map.get(key)
            if not agg:
                agg = super_edges_map[key] = {"weight": 0.0, "count": 0}
            agg["weight"] += float(e.get("weight") or 1.0)
            agg["count"] += 1

        super_edges = []
        for (x, y, kind), data in super_edges_map.items():
            super_edges.append(
                self._edge(
                    x,
                    y,
                    kind=kind,
                    relation="aggregates",
                    weight=float(data.get("weight") or 1.0),
                    meta={"count": int(data.get("count") or 0)},
                )
            )

        return {"nodes": super_nodes, "edges": super_edges, "members": members}

    def _gap_insights(self, detail: dict) -> list[dict]:
        nodes = detail.get("nodes") or []
        edges = detail.get("edges") or []
        node_by_id = {n.get("id"): n for n in nodes}

        doc_source = {n["id"]: _safe_str(n.get("source")) for n in nodes if str(n.get("id", "")).startswith("doc:")}
        jira_docs = {nid for nid, src in doc_source.items() if src == "jira"}
        conf_docs = {nid for nid, src in doc_source.items() if src == "confluence"}
        slack_docs = {nid for nid, src in doc_source.items() if src == "slack"}

        connected_to_jira: set[str] = set()
        connected_to_conf: set[str] = set()

        for e in edges:
            if _safe_str(e.get("kind")) not in {"explicit", "semantic"}:
                continue
            a = _safe_str(e.get("source"))
            b = _safe_str(e.get("target"))
            if a in slack_docs and b in jira_docs:
                connected_to_jira.add(a)
            if b in slack_docs and a in jira_docs:
                connected_to_jira.add(b)
            if a in jira_docs and b in conf_docs:
                connected_to_conf.add(a)
            if b in jira_docs and a in conf_docs:
                connected_to_conf.add(b)

        # Slack: group by channel (stable for "dense discussion").
        slack_by_channel: dict[str, list[str]] = defaultdict(list)
        for nid in slack_docs:
            meta = _jsonish((node_by_id.get(nid) or {}).get("meta"))
            cid = _safe_str(meta.get("channel_id")) or "unknown"
            slack_by_channel[cid].append(nid)

        insights: list[dict] = []

        # Case 1: discussion without action.
        for cid, ids in slack_by_channel.items():
            if len(ids) < 4:
                continue
            if not any(d in connected_to_jira for d in ids):
                meta0 = _jsonish((node_by_id.get(ids[0]) or {}).get("meta"))
                label = _safe_str(meta0.get("channel_name")) or cid
                insights.append(
                    {
                        "type": "gap_discussion_no_action",
                        "severity": "warning",
                        "title": "Có thảo luận, chưa có Action",
                        "detail": f"Slack channel '{label}' có {len(ids)} cụm thảo luận nhưng chưa nối sang Jira.",
                        "example_nodes": ids[:6],
                    }
                )

        # Case 2: action without spec.
        lonely_jira = sorted([jid for jid in jira_docs if jid not in connected_to_conf])
        if len(lonely_jira) >= 6:
            insights.append(
                {
                    "type": "gap_action_no_spec",
                    "severity": "warning",
                    "title": "Có Action, thiếu Đặc tả",
                    "detail": f"Có {len(lonely_jira)} Jira issues chưa liên kết với Confluence pages.",
                    "example_nodes": lonely_jira[:8],
                }
            )

        return insights

    def _bfs_highlight(self, detail: dict, *, root: str, depth: int) -> dict:
        nodes = detail.get("nodes") or []
        edges = detail.get("edges") or []
        node_ids = {n.get("id") for n in nodes}

        adj: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for e in edges:
            a = _safe_str(e.get("source"))
            b = _safe_str(e.get("target"))
            if a not in node_ids or b not in node_ids:
                continue
            adj[a].append((b, e))
            adj[b].append((a, e))

        root = _safe_str(root)
        if root not in node_ids:
            return {"error": "Root node is not in graph"}

        visited: set[str] = {root}
        frontier: list[str] = [root]
        used_edges: set[str] = set()

        def ek(e: dict) -> str:
            return f"{e.get('source')}|{e.get('target')}|{e.get('kind')}|{e.get('relation')}"

        for _ in range(max(1, int(depth))):
            nxt: list[str] = []
            for u in frontier:
                for v, e in adj.get(u, []):
                    if v not in visited:
                        visited.add(v)
                        nxt.append(v)
                    used_edges.add(ek(e))
            frontier = nxt
            if not frontier:
                break

        return {"root": root, "highlight_nodes": sorted(visited), "highlight_edges": sorted(used_edges)}

    def _crop_by_bfs(self, nodes: list[dict], edges: list[dict], *, roots: list[str], depth: int) -> dict:
        node_ids = {str(n.get("id") or "") for n in nodes}
        roots = [str(r) for r in (roots or []) if str(r) in node_ids]
        if not roots:
            return {"nodes": nodes, "edges": edges}

        adj: dict[str, list[str]] = defaultdict(list)
        for e in edges:
            a = _safe_str(e.get("source"))
            b = _safe_str(e.get("target"))
            if a in node_ids and b in node_ids:
                adj[a].append(b)
                adj[b].append(a)

        keep: set[str] = set(roots)
        frontier: list[str] = list(roots)
        for _ in range(max(1, int(depth))):
            nxt: list[str] = []
            for u in frontier:
                for v in adj.get(u, []):
                    if v not in keep:
                        keep.add(v)
                        nxt.append(v)
            frontier = nxt
            if not frontier:
                break

        kept_nodes = [n for n in nodes if _safe_str(n.get("id")) in keep]
        keep_set = {_safe_str(n.get("id")) for n in kept_nodes}
        kept_edges = [e for e in edges if _safe_str(e.get("source")) in keep_set and _safe_str(e.get("target")) in keep_set]
        return {"nodes": kept_nodes, "edges": kept_edges}

    def _doc_node(self, doc: DocRow) -> dict:
        meta = _jsonish(doc.metadata)
        source = doc.source

        if source == "jira":
            issue_type = _safe_str(meta.get("issue_type"))
            subkind = issue_type.lower() if issue_type else "issue"
            return {
                "id": f"doc:{doc.id}",
                "kind": "jira",
                "source": source,
                "subkind": subkind,
                "label": doc.title or f"jira:{doc.id[:8]}",
                "color": GraphPalette.JIRA,
                "icon": subkind or "jira",
                "url": doc.url or "",
                "created_at": _iso_date(doc.updated_at),
                "updated_at": _iso_date(doc.updated_at),
                "meta": {**meta, "topic_key": self._topic_key_for_doc(doc)},
            }

        if source == "confluence":
            subkind = self._classify_confluence_page(doc.title)
            return {
                "id": f"doc:{doc.id}",
                "kind": "confluence",
                "source": source,
                "subkind": subkind,
                "label": doc.title or f"confluence:{doc.id[:8]}",
                "color": GraphPalette.CONFLUENCE,
                "icon": subkind,
                "url": doc.url or "",
                "created_at": _iso_date(doc.updated_at),
                "updated_at": _iso_date(doc.updated_at),
                "meta": {**meta, "topic_key": self._topic_key_for_doc(doc)},
            }

        if source == "slack":
            return {
                "id": f"doc:{doc.id}",
                "kind": "slack",
                "source": source,
                "subkind": "thread",
                "label": doc.title or f"slack:{doc.id[:8]}",
                "color": GraphPalette.SLACK,
                "icon": "slack",
                "url": doc.url or "",
                "created_at": _iso_date(doc.updated_at),
                "updated_at": _iso_date(doc.updated_at),
                "meta": {**meta, "topic_key": self._topic_key_for_doc(doc)},
            }

        if source == "file_server":
            subkind = self._classify_file(meta)
            return {
                "id": f"doc:{doc.id}",
                "kind": "file",
                "source": source,
                "subkind": subkind,
                "label": doc.title or f"file:{doc.id[:8]}",
                "color": GraphPalette.FILE,
                "icon": "file",
                "url": doc.url or "",
                "created_at": _iso_date(doc.updated_at),
                "updated_at": _iso_date(doc.updated_at),
                "meta": {**meta, "topic_key": self._topic_key_for_doc(doc)},
            }

        return {
            "id": f"doc:{doc.id}",
            "kind": "doc",
            "source": source or "doc",
            "subkind": "doc",
            "label": doc.title or f"{source}:{doc.id[:8]}",
            "color": "#94A3B8",
            "icon": "doc",
            "url": doc.url or "",
            "meta": {**meta, "topic_key": self._topic_key_for_doc(doc)},
        }

    def _parent_node_for_doc(self, doc: DocRow) -> dict | None:
        meta = _jsonish(doc.metadata)
        if doc.source == "slack":
            cid = _safe_str(meta.get("channel_id"))
            if cid:
                name = _safe_str(meta.get("channel_name"))
                return {
                    "id": f"slack_channel:{cid}",
                    "kind": "slack",
                    "source": "slack",
                    "subkind": "channel",
                    "label": f"#{name or cid}",
                    "color": GraphPalette.SLACK,
                    "icon": "channel",
                    "url": f"https://slack.com/archives/{cid}",
                    "meta": {"channel_id": cid, "channel_name": name},
                }

        if doc.source == "confluence":
            sk = _safe_str(meta.get("space_key"))
            if sk:
                sn = _safe_str(meta.get("space_name"))
                return {
                    "id": f"confluence_space:{sk}",
                    "kind": "confluence",
                    "source": "confluence",
                    "subkind": "space",
                    "label": f"{sk} ({sn})" if sn else sk,
                    "color": GraphPalette.CONFLUENCE,
                    "icon": "space",
                    "url": "",
                    "meta": {"space_key": sk, "space_name": sn},
                }

        if doc.source == "file_server":
            folder = _safe_str(meta.get("top_folder"))
            if folder:
                return {
                    "id": f"file_folder:{folder}",
                    "kind": "file",
                    "source": "file_server",
                    "subkind": "folder",
                    "label": folder,
                    "color": GraphPalette.FILE,
                    "icon": "folder",
                    "url": "",
                    "meta": {"top_folder": folder},
                }

        return None

    def _edge(
        self,
        source: str,
        target: str,
        *,
        kind: str,
        relation: str,
        weight: float,
        meta: dict | None = None,
    ) -> dict:
        return {
            "source": str(source),
            "target": str(target),
            "kind": str(kind),
            "relation": str(relation),
            "weight": float(weight),
            "meta": meta or {},
        }

    def _node_size(self, node: dict) -> float:
        if node.get("kind") == "user":
            return 11.0
        if str(node.get("id", "")).startswith(("slack_channel:", "confluence_space:", "file_folder:")):
            return 12.5
        if node.get("kind") == "jira":
            return 13.0
        return 11.5

    def _roles_for_doc(self, doc: DocRow) -> dict[str, list[str]]:
        meta = _jsonish(doc.metadata)
        roles: dict[str, list[str]] = defaultdict(list)

        if doc.source == "jira":
            assignee = _normalize_person(_safe_str(meta.get("assignee_name")))
            creator = _normalize_person(_safe_str(meta.get("creator_name")))
            if assignee:
                roles[assignee].append("assignee")
            if creator:
                roles[creator].append("creator")

        if doc.source == "confluence":
            author = _normalize_person(_safe_str(meta.get("author_name") or doc.author))
            if author:
                roles[author].append("author")

        if doc.source == "slack":
            for participant in meta.get("participants") or []:
                if not isinstance(participant, dict):
                    continue
                name = _normalize_person(
                    _safe_str(participant.get("display_name") or participant.get("real_name") or participant.get("name"))
                )
                if name:
                    roles[name].append("participant")

        return roles

    def _classify_confluence_page(self, title: str) -> str:
        t = _safe_str(title).lower()
        if any(x in t for x in ("srs", "brd", "spec", "requirement")):
            return "spec"
        if "api" in t or "swagger" in t:
            return "api_doc"
        if "release" in t or "changelog" in t:
            return "release_notes"
        return "page"

    def _classify_file(self, meta: dict) -> str:
        ext = _safe_str(meta.get("extension")).lower().lstrip(".")
        if ext == "pdf":
            return "pdf"
        if ext in {"doc", "docx"}:
            return "word"
        if ext in {"xls", "xlsx"}:
            return "excel"
        if ext in {"vsdx", "drawio"}:
            return "diagram"
        return ext or "file"

    def _topic_key_for_doc(self, doc: DocRow) -> str:
        meta = _jsonish(doc.metadata)
        extracted = meta.get("entities") or []
        projects: list[str] = []
        services: list[str] = []
        for e in extracted:
            if not isinstance(e, dict):
                continue
            name = _safe_str(e.get("name"))
            typ = _safe_str(e.get("type"))
            if typ == "project" and name:
                projects.append(name.upper())
            if typ == "service" and name:
                services.append(name.lower())

        if projects:
            return projects[0]
        if services:
            return services[0].split(" ", 1)[0]

        if doc.source == "jira":
            return _safe_str(meta.get("project_key")).upper() or "JIRA"
        if doc.source == "confluence":
            return _safe_str(meta.get("space_key")).upper() or "CONFLUENCE"
        if doc.source == "slack":
            return _safe_str(meta.get("channel_name")).lower() or "slack"
        if doc.source == "file_server":
            return _safe_str(meta.get("top_folder")).lower() or "files"
        return doc.source or "docs"

    def _fallback_topic(self, doc_node: dict) -> str:
        meta = _jsonish(doc_node.get("meta"))
        src = _safe_str(doc_node.get("source"))
        if src == "slack":
            return _safe_str(meta.get("channel_name")).lower() or "slack"
        if src == "confluence":
            return _safe_str(meta.get("space_key")).upper() or "CONFLUENCE"
        if src == "file_server":
            return _safe_str(meta.get("top_folder")).lower() or "files"
        if src == "jira":
            return _safe_str(meta.get("project_key")).upper() or "JIRA"
        return src or "docs"
