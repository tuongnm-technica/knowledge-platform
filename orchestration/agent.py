"""
Main agent orchestration.
"""

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import re

from config.settings import settings
from graph.knowledge_graph import KnowledgeGraph
from models.query import SearchQuery, SearchResult
from orchestration.react_loop import ReActLoop, ReActResult
from orchestration.tools import build_tool_registry
from permissions.filter import PermissionFilter
from persistence.document_repository import DocumentRepository
from persistence.asset_repository import AssetRepository
from ranking.scorer import RankingScorer
from retrieval.hybrid.hybrid_search import HybridSearch
from utils.vision_answer import answer_with_images


log = structlog.get_logger()


class OllamaLLM:
    def __init__(self):
        self._base = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

    async def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            try:
                resp = await client.post(f"{self._base}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
            except httpx.TimeoutException:
                raise RuntimeError(f"Ollama timed out ({settings.LLM_TIMEOUT}s)")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Ollama error {e.response.status_code}")

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


class Agent:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._search = HybridSearch(session)
        self._permissions = PermissionFilter(session)
        self._scorer = RankingScorer()
        self._repo = DocumentRepository(session)
        self._graph = KnowledgeGraph(session)
        self._llm = OllamaLLM()

    async def ask(self, question: str, user_id: str) -> dict:
        tools = build_tool_registry(self._session)
        loop = ReActLoop(tools, max_iterations=settings.AGENT_MAX_STEPS)
        try:
            result: ReActResult = await loop.run(question, user_id=user_id)
        finally:
            try:
                await loop.close()
            except Exception:
                pass

        sources = self._format_sources(result.sources)

        # Optional: run a final vision-aware answer pass if we have image assets for the retrieved chunks.
        # Captions are already injected into text, but vision can answer "explain this diagram/screenshot" more reliably.
        if settings.VISION_ENABLED and str(settings.OLLAMA_VISION_MODEL or "").strip():
            try:
                chunk_ids = [str(s.get("chunk_id") or "").strip() for s in (result.sources or []) if str(s.get("chunk_id") or "").strip()]
                chunk_ids = list(dict.fromkeys(chunk_ids))[:12]
                assets_by_chunk = await AssetRepository(self._session).assets_for_chunks(chunk_ids)

                picked: list[str] = []
                for cid in chunk_ids:
                    for a in (assets_by_chunk.get(cid) or []):
                        aid = str(a.get("asset_id") or "").strip()
                        if aid and aid not in picked:
                            picked.append(aid)
                        if len(picked) >= int(settings.VISION_MAX_IMAGES_PER_ANSWER or 2):
                            break
                    if len(picked) >= int(settings.VISION_MAX_IMAGES_PER_ANSWER or 2):
                        break

                images: list[bytes] = []
                assets_dir = Path(settings.ASSETS_DIR or "assets")
                for cid in chunk_ids:
                    for a in (assets_by_chunk.get(cid) or []):
                        aid = str(a.get("asset_id") or "").strip()
                        if aid not in picked:
                            continue
                        rel = str(a.get("local_path") or "").strip().replace("\\", "/")
                        if not rel:
                            continue
                        try:
                            images.append((assets_dir / rel).read_bytes())
                        except Exception:
                            continue

                # Build a compact text context for the vision pass.
                blocks: list[str] = []
                for s in (result.sources or [])[:6]:
                    title = str(s.get("title") or "").strip()
                    content = str(s.get("content") or "").strip()
                    content = re.sub(r"\\[\\[ASSET_ID:[0-9a-fA-F-]{36}\\]\\]", "", content).strip()
                    if not content:
                        continue
                    blocks.append(f"TITLE: {title}\n{content[:1800]}".strip())
                vision_context = "\n\n---\n\n".join(blocks)[:12000]

                if images:
                    vision_out = await answer_with_images(question=question, context=vision_context, images=images)
                    if vision_out:
                        result.answer = vision_out
                        if "vision_answer" not in (result.used_tools or []):
                            result.used_tools.append("vision_answer")
            except Exception:
                pass

        log.info(
            "agent.ask.done",
            question=question[:60],
            iterations=len(result.steps),
            used_tools=result.used_tools,
            sources=len(sources),
        )

        return {
            "answer": result.answer,
            "sources": sources,
            "rewritten_query": result.rewritten_query or question,
            "agent_steps": self._format_steps(result.steps),
            "agent_plan": [{"step": p.step, "tool": p.tool, "reason": p.reason} for p in result.plan],
            "used_tools": result.used_tools,
        }

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        allowed_ids = await self._permissions.allowed_docs(query.user_id)
        # If the user is not admin and has no ACL matches, return no results (permission-aware retrieval).
        if allowed_ids is not None and len(allowed_ids) == 0:
            return []
        graph_doc_ids = await self._graph.find_related_documents(
            query.entities,
            limit=max(query.limit * 5, 20),
        )
        if allowed_ids:
            allowed_set = {str(doc_id) for doc_id in allowed_ids}
            graph_doc_ids = [doc_id for doc_id in graph_doc_ids if str(doc_id) in allowed_set]

        raw = await self._search.search(
            query.effective,
            top_k=max(query.limit * 3, 20),
            allowed_document_ids=allowed_ids,
        )
        raw = self._apply_graph_boost(raw, query, graph_doc_ids)

        doc_ids = list({str(item["document_id"]) for item in raw if item.get("document_id")})
        doc_ids.extend([doc_id for doc_id in graph_doc_ids if doc_id not in doc_ids])
        doc_meta = await self._fetch_doc_meta(doc_ids)
        raw.extend(self._supplement_graph_results(graph_doc_ids, raw, doc_meta, query))

        scored = self._scorer.score(raw, doc_meta)
        return self._to_results(scored[:query.limit], doc_meta)

    async def health(self) -> dict:
        ollama_ok = await self._llm.is_available()
        return {
            "ollama": "ok" if ollama_ok else "unavailable",
            "ollama_model": settings.OLLAMA_LLM_MODEL,
            "ollama_url": settings.OLLAMA_BASE_URL,
            "embedding_model": settings.EMBEDDING_MODEL,
        }

    def _apply_graph_boost(self, raw: list[dict], query: SearchQuery, graph_doc_ids: list[str]) -> list[dict]:
        graph_hits = {str(doc_id) for doc_id in graph_doc_ids}
        for item in raw:
            item["query"] = query.effective
            item["graph_score"] = 1.0 if str(item.get("document_id", "")) in graph_hits else 0.0
        return raw

    def _supplement_graph_results(
        self,
        graph_doc_ids: list[str],
        raw: list[dict],
        doc_meta: dict[str, dict],
        query: SearchQuery,
    ) -> list[dict]:
        existing_doc_ids = {str(item.get("document_id", "")) for item in raw}
        supplemented = []
        for doc_id in graph_doc_ids:
            if doc_id in existing_doc_ids:
                continue
            meta = doc_meta.get(doc_id)
            if not meta:
                continue
            supplemented.append(
                {
                    "document_id": doc_id,
                    "chunk_id": "",
                    "content": (meta.get("content") or "")[:500],
                    "source": meta.get("source", ""),
                    "title": meta.get("title", ""),
                    "vector_score": 0.0,
                    "keyword_score": 0.0,
                    "graph_score": 1.0,
                    "query": query.effective,
                }
            )
        return supplemented

    def _format_sources(self, raw_sources: list[dict]) -> list[dict]:
        seen: dict[str, dict] = {}
        for source in raw_sources:
            url = source.get("url") or source.get("document_id", "")
            if url and url not in seen:
                seen[url] = {
                    "title": source.get("title", "Untitled"),
                    "url": source.get("url", ""),
                    "source": source.get("source", ""),
                    "score": round(source.get("score", 0), 3),
                    "snippet": source.get("content", "")[:150],
                    "document_id": source.get("document_id", ""),
                    "chunk_id": source.get("chunk_id", ""),
                    "assets": source.get("assets") or [],
                }
        return list(seen.values())

    def _format_steps(self, steps) -> list[dict]:
        return [
            {
                "iteration": step.iteration,
                "thought": step.thought,
                "action": step.action,
                "action_input": step.action_input,
                "observation": step.observation[:300] if step.observation else "",
                "is_final": step.is_final,
            }
            for step in steps
        ]

    async def _fetch_doc_meta(self, doc_ids: list[str]) -> dict[str, dict]:
        if not doc_ids:
            return {}
        rows = await self._repo.get_by_ids(doc_ids)
        return {row["id"]: row for row in rows}

    def _to_results(self, scored: list[dict], doc_meta: dict[str, dict]) -> list[SearchResult]:
        import json
        import re

        slack_ts_re = re.compile(r"^\[\d{2}:\d{2}\|([0-9]+\.[0-9]+)\]", re.MULTILINE)

        def _jsonish(value):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value) if value else {}
                except Exception:
                    return {}
            return {}

        def _slack_deep_link(channel_id: str, ts: str) -> str:
            ts = str(ts or "").strip()
            if not ts:
                return f"https://slack.com/archives/{channel_id}"
            if "." in ts:
                sec, frac = ts.split(".", 1)
                frac = (frac + "000000")[:6]
                ts_digits = f"{sec}{frac}"
            else:
                ts_digits = "".join([c for c in ts if c.isdigit()])
            return f"https://slack.com/archives/{channel_id}/p{ts_digits}"

        results: list[SearchResult] = []
        for item in scored:
            doc_id = str(item.get("document_id", ""))
            meta = doc_meta.get(doc_id, {})

            url = meta.get("url", "")
            source = meta.get("source", "")
            content = item.get("content", "")

            # Slack: override doc.url with per-chunk deep link if we can extract ts from the chunk content.
            if source == "slack" and content:
                md = _jsonish(meta.get("metadata"))
                channel_id = str(md.get("channel_id") or "").strip()
                m = slack_ts_re.search(content)
                if channel_id and m:
                    url = _slack_deep_link(channel_id, m.group(1))

            results.append(
                SearchResult(
                    document_id=doc_id,
                    chunk_id=str(item.get("chunk_id", "")),
                    title=meta.get("title", "Unknown"),
                    content=content,
                    url=url,
                    source=source,
                    author=meta.get("author", ""),
                    score=item.get("final_score", 0.0),
                    score_breakdown=item.get("score_breakdown", {}),
                )
            )
        return results
