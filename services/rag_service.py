import structlog
import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.query import SearchQuery, SearchResult
from services.embedding_service import get_embedding_service
from retrieval.hybrid.hybrid_search import HybridSearch
from permissions.filter import PermissionFilter
from graph.knowledge_graph import KnowledgeGraph
from ranking.scorer import RankingScorer
from persistence.document_repository import DocumentRepository
from services.context_builder import ContextBuilder

from retrieval.query_expansion import expand_query
from retrieval.reranker import rerank
from storage.vector.vector_store import VectorStore, recreate_collection
from persistence.asset_repository import AssetRepository

log = structlog.get_logger()

# Scopes for Graph Relation weights (Lỗi #3: Source Trust Fix)
RELATION_TYPE_SCORES = {
    "depends_on": 1.0,
    "part_of": 0.9,
    "causes": 0.8,
    "triggers": 0.8,
    "implements": 0.9,
}

class RAGService:
    """
    Dịch vụ điều phối RAG (Retrieval-Augmented Generation) cho MyGPT SDLC Suite.
    Thành phần cốt lõi trong phân hệ RAG & Reranker Engine (Phần 5.4 tài liệu thiết kế).
    
    Quy trình xử lý:
    1. Kiểm tra phân quyền (RBAC) dựa trên Group của User.
    2. Query Rewrite: Làm sạch câu truy vấn bằng LLM.
    3. Hybrid Search: Kết hợp Vector (Qdrant) và Keyword (Postgres).
    4. GraphRAG Augmentation: Củng cố ngữ cảnh bằng dữ liệu từ Đồ thị Tri thức.
    5. Multi-stage Reranking: Chấm điểm lại bằng Cross-encoder (reranker.py).
    6. Vision Answer: Xử lý đa phương thức nếu có hình ảnh/diagram đính kèm.
    """
    @staticmethod
    def clear_all():
        """ Recreate standard collections. """
        recreate_collection(settings.QDRANT_COLLECTION, size=settings.VECTOR_DIM)
        recreate_collection("semantic_cache", size=settings.VECTOR_DIM)
        log.info("rag_service.clear_all.done")

    @staticmethod
    def delete_by_sources(sources: List[str]):
        """ Delete vectors for specific sources. """
        VectorStore().delete_by_sources(sources)
        log.info("rag_service.delete_by_sources.done", sources=sources)
    def __init__(self, session: AsyncSession, user_id: str):
        self._session = session
        self._user_id = user_id
        
        # Components
        self._search = HybridSearch(session)
        self._permissions = PermissionFilter(session)
        self._graph = KnowledgeGraph(session)
        self._scorer = RankingScorer()
        self._repo = DocumentRepository(session)
        self._assets = AssetRepository(session)
        self._embedding_service = get_embedding_service()

    async def searchv2(
        self, 
        query_text: str, 
        limit: int = 5, 
        source: str = "all",
        expand: bool = False,
        use_rerank: bool = False,
        include_context: bool = False,
        context_window: int = 3,
        need_graph: bool = False,
        intent: str = "general"
    ) -> Dict[str, Any]:
        """ 
        Advanced search for Agent Tools. 
        Returns a dict with 'hits' and 'relationships'.
        """
        # 1. Permission Check
        allowed_ids = await self._permissions.allowed_docs(self._user_id)
        if allowed_ids is not None and len(allowed_ids) == 0:
            return []

        # 2. Query Expansion
        queries = [query_text]
        if expand and settings.QUERY_EXPANSION_ENABLED:
            queries = await expand_query(query_text, use_llm=True)
            log.info("rag_service.expanded", original=query_text, expanded=queries)

        # 3. Parallel Hybrid Search
        tasks = [
            self._search.search(
                q,
                top_k=max(limit * 5, 50),
                allowed_document_ids=allowed_ids,
            ) for q in queries
        ]
        
        search_results = await asyncio.gather(*tasks)
        all_hits = []
        for hits in search_results:
            all_hits.extend(hits)
        
        # Deduplicate hits by chunk_id
        seen = set()
        unique_hits = []
        for h in all_hits:
            cid = h.get("chunk_id")
            if cid not in seen:
                seen.add(cid)
                unique_hits.append(h)
        
        # 4. Filter by Source
        if source != "all":
            unique_hits = [h for h in unique_hits if h.get("source") == source]

        if not unique_hits:
            return []

        # 4.5 Graph-based Augmentation (Multi-hop)
        # Discover related documents through graph entities
        graph_doc_ids = []
        neighbor_relationships = []
        if need_graph and getattr(settings, "GRAPH_AUGMENTATION_ENABLED", True):
            try:
                # Use entities from top results as seeds for graph traversal
                seed_doc_ids = list({str(h["document_id"]) for h in unique_hits[:10]})
                seed_meta = await self._fetch_doc_meta(seed_doc_ids)
                
                seed_entities = set()
                for meta in seed_meta.values():
                    seed_entities.update(meta.get("entities") or [])
                
                if seed_entities:
                    allowed_relations = list(RELATION_TYPE_SCORES.keys())
                    # Ngân sách Expansion: Giới hạn tối đa 5 seed entities (Lỗi #4: Expansion Budget)
                    max_entities = 5
                    tasks = [self._graph.find_related_entities(ent, min_weight=2, limit=3, allowed_relations=allowed_relations) for ent in list(seed_entities)[:max_entities]]
                    neighbor_results = await asyncio.gather(*tasks)
                    
                    # Track relationships for prompt construction and store weights for scoring
                    neighbor_entity_weights = {} # entity_name -> max_calculated_score
                    used_edges = [] # list[relation_id]
                    for i, seed in enumerate(list(seed_entities)[:max_entities]):
                        for name, weight, rel_id in neighbor_results[i]:
                            # In current Hop 1: hop_distance = 1
                            # graph_score = weight * relation_type_score / hop_distance
                            rel_type = "related" # Standard label for context
                            type_score = 0.5 # Default if unknown
                            # We don't have rel_type here easily from find_related_entities yet, 
                            # but we can improve find_related_entities later if needed.
                            # For now use the weight directly normalized.
                            score = (weight * type_score) / 1.0
                            neighbor_entity_weights[name] = max(neighbor_entity_weights.get(name, 0), score)
                            neighbor_relationships.append(f"({seed}) --[related]--> ({name})")
                            if rel_id:
                                used_edges.append(rel_id)

                    neighbor_entities = list(neighbor_entity_weights.keys())
                    
                    if neighbor_entities:
                        # Hop 2: Documents for these neighbor entities (Budget: max 5 docs)
                        max_docs = 5
                        graph_doc_ids = await self._graph.find_related_documents(neighbor_entities, limit=max_docs)
                        
                        # Pre-map doc_id to its graph score contribution from entities
                        # A doc can be related to multiple neighbor entities, take the best one.
                        self._doc_graph_scores = {}
                        for ent_name in neighbor_entities:
                            ent_score = neighbor_entity_weights[ent_name]
                            # Find all docs connected to this entity
                            docs = await self._graph.find_related_documents([ent_name], limit=10)
                            for d_id in docs:
                                self._doc_graph_scores[str(d_id)] = max(self._doc_graph_scores.get(str(d_id), 0), ent_score)

                        log.info("rag_service.graph_augmentation", seed_entities=len(seed_entities), neighbors=len(neighbor_entities), found_docs=len(graph_doc_ids))
            except Exception as e:
                log.warning("rag_service.graph_augmentation.failed", error=str(e))

        # 5. Metadata Enrichment
        # Collect all doc IDs including graph-discovered ones
        all_doc_ids = list({str(h["document_id"]) for h in unique_hits} | set(graph_doc_ids))
        doc_meta = await self._fetch_doc_meta(all_doc_ids)
        
        # Supplement hits with graph-discovered documents if not already present
        if graph_doc_ids:
            supplemented = self._supplement_graph_results(graph_doc_ids, unique_hits, doc_meta, query_text)
            unique_hits.extend(supplemented)
        
        # 6. Initial Scoring & Fusion (Dynamic Scoring based on Intent)
        # Apply the granular graph scores to all hits before scoring
        for h in unique_hits:
            d_id = str(h.get("document_id"))
            # Normalizing to 0-1 range (assuming weight 10-20 is very strong)
            raw_graph_score = getattr(self, "_doc_graph_scores", {}).get(d_id, 0.0)
            h["graph_score"] = min(1.0, raw_graph_score / 10.0) 

        scored = self._scorer.score(unique_hits, doc_meta, intent=intent)
        
        # 7. Reranking (Multi-stage)
        if use_rerank and settings.RERANKING_ENABLED:
            # Stage 1: Fast Rerank (Shortlist the top 25 from the initial scoring)
            shortlist = scored[:max(limit * 4, 25)]
            
            # Stage 2: Full Rerank (LLM or Cross-Encoder)
            shortlist = await rerank(query=query_text, candidates=shortlist, top_k=limit)
        else:
            shortlist = scored[:limit]

        # 8. Context Window & Assets
        results = []
        chunk_ids = [str(h.get("chunk_id")) for h in shortlist if h.get("chunk_id")]
        assets_by_chunk = await self._assets.assets_for_chunks(chunk_ids) if chunk_ids else {}

        for h in shortlist:
            doc_id = str(h["document_id"])
            chunk_id = str(h["chunk_id"])
            meta = doc_meta.get(doc_id, {})
            
            content = h.get("content", "")
            if include_context and chunk_id:
                try:
                    # RAG + Reasoning: Kéo trọn Parent Section Context thay vì chỉ Neighbor
                    parent_id = h.get("parent_chunk_id") # Cần DB hit trả về parent_chunk_id
                    if parent_id:
                        section_chunks = await self._repo.get_section_chunks(parent_id)
                        if section_chunks:
                            # Context Overload Protection: Kiểm soát Token Explosion
                            total_chars = sum(len(c["content"]) for c in section_chunks)
                            if total_chars < 8000: # Ngưỡng ~2000 tokens, Expand full section an toàn
                                content = "\n".join([c["content"] for c in section_chunks])
                            else:
                                # Section quá to -> Selective expand quanh chunk hiện tại
                                neighbors = await self._repo.get_neighbor_chunks(chunk_id, window=context_window)
                                if neighbors:
                                    content = "[(Cảnh báo: Section quá dài, đã truncate)]\n" + "\n".join([c["content"] for c in neighbors])
                    else:
                        # Fallback về neighbor nếu file chưa có cấu trúc
                        neighbors = await self._repo.get_neighbor_chunks(chunk_id, window=context_window)
                        if neighbors:
                            content = "\n".join([c["content"] for c in neighbors])
                except Exception:
                    pass

            # NEW: Nếu là cuộc họp, hãy cố gắng lấy thêm SUMMARY nếu chưa có trong content
            if meta.get("source") in ("zoom", "google_meet") and "[SUMMARY]" not in content:
                try:
                    full_doc = doc_meta.get(doc_id, {})
                    raw_content = full_doc.get("content", "")
                    m = re.search(r"(\[SUMMARY\].*?\[/SUMMARY\])", raw_content, re.DOTALL)
                    if m:
                        content = f"{m.group(1)}\n\n---\n\n{content}"
                except Exception:
                    pass
            
            # Formatting (Slack deep link etc)
            url = meta.get("url", "")
            if meta.get("source") == "slack" and content:
                from connectors.slack.utils import slack_deep_link
                m = re.search(r"^\[\d{2}:\d{2}\|([0-9]+\.[0-9]+)\]", content, re.MULTILINE)
                if m:
                    md = self._jsonish(meta.get("metadata"))
                    url = slack_deep_link(str(md.get("channel_id")), m.group(1))

            results.append({
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "title": meta.get("title", "Untitled"),
                "source": meta.get("source", "unknown"),
                "url": url,
                "content": content,
                "score": round(float(h.get("rerank_score") or h.get("final_score") or 0.0), 3),
                "assets": [
                    {
                        "asset_id": str(a.get("asset_id")),
                        "caption": str(a.get("caption")),
                        "url": f"/assets/{str(a.get('asset_id'))}"
                    } for a in (assets_by_chunk.get(chunk_id) or [])
                ]
            })

        # Multi-source Reasoning: Group by document source via ContextBuilder
        grouped_results = ContextBuilder.build(results)

        return {
            "hits": grouped_results,
            "relationships": list(set(neighbor_relationships)),
            "used_edges": list(set(used_edges)) if 'used_edges' in locals() else []
        }

    def _jsonish(self, value):
        if isinstance(value, dict): return value
        try: return json.loads(value) if value else {}
        except: return {}

    def _apply_graph_boost(self, raw: List[Dict], query_text: str, graph_doc_ids: List[str]) -> List[Dict]:
        graph_hits = {str(doc_id) for doc_id in graph_doc_ids}
        for item in raw:
            item["query"] = query_text
            item["graph_score"] = 1.0 if str(item.get("document_id", "")) in graph_hits else 0.0
        return raw

    def _supplement_graph_results(self, graph_doc_ids: List[str], raw: List[Dict], doc_meta: Dict[str, Dict], query_text: str) -> List[Dict]:
        existing_doc_ids = {str(item.get("document_id", "")) for item in raw}
        supplemented = []
        for doc_id in graph_doc_ids:
            if doc_id in existing_doc_ids:
                continue
            meta = doc_meta.get(doc_id)
            if not meta:
                continue
            supplemented.append({
                "document_id": doc_id,
                "chunk_id": "",
                "content": (meta.get("content") or "")[:500],
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "graph_score": 1.0,
                "query": query_text,
            })
        return supplemented

    async def _fetch_doc_meta(self, doc_ids: List[str]) -> Dict[str, Dict]:
        if not doc_ids:
            return {}
        rows = await self._repo.get_by_ids(doc_ids)
        return {row["id"]: row for row in rows}

    def _to_search_results(self, scored: List[Dict], doc_meta: Dict[str, Dict]) -> List[SearchResult]:
        slack_ts_re = re.compile(r"^\[\d{2}:\d{2}\|([0-9]+\.[0-9]+)\]", re.MULTILINE)

        def _jsonish(value):
            if isinstance(value, dict): return value
            try: return json.loads(value) if value else {}
            except: return {}

        def _slack_deep_link(channel_id: str, ts: str) -> str:
            ts = str(ts or "").strip()
            if not ts: return f"https://slack.com/archives/{channel_id}"
            if "." in ts:
                sec, frac = ts.split(".", 1)
                ts_digits = f"{sec}{(frac + '000000')[:6]}"
            else:
                ts_digits = "".join([c for c in ts if c.isdigit()])
            return f"https://slack.com/archives/{channel_id}/p{ts_digits}"

        results = []
        for item in scored:
            doc_id = str(item.get("document_id", ""))
            meta = doc_meta.get(doc_id, {})
            url = meta.get("url", "")
            source = meta.get("source", "")
            content = item.get("content", "")

            if source == "slack" and content:
                md = _jsonish(meta.get("metadata"))
                channel_id = str(md.get("channel_id") or "").strip()
                m = slack_ts_re.search(content)
                if channel_id and m:
                    url = _slack_deep_link(channel_id, m.group(1))

            results.append(SearchResult(
                document_id=doc_id,
                chunk_id=str(item.get("chunk_id", "")),
                title=meta.get("title", "Unknown"),
                content=content,
                url=url,
                source=source,
                author=meta.get("author", ""),
                score=item.get("final_score", 0.0),
                score_breakdown=item.get("score_breakdown", {}),
            ))
        return results
