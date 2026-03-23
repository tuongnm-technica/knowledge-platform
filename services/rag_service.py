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

from retrieval.query_expansion import expand_query
from retrieval.reranker import rerank
from storage.vector.vector_store import VectorStore, recreate_collection
from persistence.asset_repository import AssetRepository

log = structlog.get_logger(__name__)

class RAGService:
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
        context_window: int = 3
    ) -> List[Dict[str, Any]]:
        """ 
        Advanced search for Agent Tools. 
        Returns a list of dicts suitable for LLM observation.
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

        # 5. Metadata Enrichment
        doc_ids = list({str(h["document_id"]) for h in unique_hits})
        doc_meta = await self._fetch_doc_meta(doc_ids)
        
        for h in unique_hits:
            h["query"] = query_text # for scoring

        # 6. Initial Scoring
        scored = self._scorer.score(unique_hits, doc_meta)
        
        # 7. Reranking
        if use_rerank and settings.RERANKING_ENABLED:
            shortlist = scored[:max(limit * 3, 20)]
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
                    neighbors = await self._repo.get_neighbor_chunks(chunk_id, window=context_window)
                    if neighbors:
                        content = "\n".join([c["content"] for c in neighbors])
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

        return results

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
