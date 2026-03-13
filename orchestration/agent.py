"""
orchestration/agent.py
Agent chính — tích hợp ReAct loop.

Backward compatible: giữ nguyên interface ask() / search() / health()
nên không cần sửa routes.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from models.query import SearchQuery, SearchResult
from retrieval.hybrid.hybrid_search import HybridSearch
from permissions.filter import PermissionFilter
from ranking.scorer import RankingScorer
from persistence.document_repository import DocumentRepository
from orchestration.react_loop import ReActLoop, ReActResult
from orchestration.tools import build_tool_registry
from config.settings import settings
import httpx
import structlog

log = structlog.get_logger()


class OllamaLLM:
    """Thin async wrapper around Ollama REST API (local)."""

    def __init__(self):
        self._base  = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

    async def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        payload = {
            "model":   self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream":  False,
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
                r = await client.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except Exception:
            return False


class Agent:
    def __init__(self, session: AsyncSession):
        self._session     = session
        self._search      = HybridSearch(session)
        self._permissions = PermissionFilter(session)
        self._scorer      = RankingScorer()
        self._repo        = DocumentRepository(session)
        self._llm         = OllamaLLM()

    # ─── Public API ─────────────────────────────────────────────────────────

    async def ask(self, question: str, user_id: str) -> dict:
        """
        ReAct agentic pipeline:
          question → ReAct loop (multi-step) → answer + sources + steps
        """
        tools  = build_tool_registry(self._session)
        loop   = ReActLoop(tools, max_iterations=settings.AGENT_MAX_STEPS)
        result: ReActResult = await loop.run(question, user_id=user_id)

        # Format sources cho UI (deduplicate theo url)
        sources = self._format_sources(result.sources)

        log.info(
            "agent.ask.done",
            question=question[:60],
            iterations=len(result.steps),
            used_tools=result.used_tools,
            sources=len(sources),
        )

        return {
            "answer":          result.answer,
            "sources":         sources,
            "rewritten_query": question,
            "agent_steps":     self._format_steps(result.steps),
            "agent_plan":      [{"step": p.step, "tool": p.tool, "reason": p.reason}
                                 for p in result.plan],
            "used_tools":      result.used_tools,
        }

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search without LLM — giữ nguyên như cũ."""
        allowed_ids = await self._permissions.allowed_docs(query.user_id)
        raw = await self._search.search(
            query.effective, top_k=query.limit,
            allowed_document_ids=allowed_ids,
        )
        doc_ids  = list({str(r["document_id"]) for r in raw})
        doc_meta = await self._fetch_doc_meta(doc_ids)
        scored   = self._scorer.score(raw, doc_meta)
        return self._to_results(scored, doc_meta)

    async def health(self) -> dict:
        ollama_ok = await self._llm.is_available()
        return {
            "ollama":          "ok" if ollama_ok else "unavailable",
            "ollama_model":    settings.OLLAMA_LLM_MODEL,
            "ollama_url":      settings.OLLAMA_BASE_URL,
            "embedding_model": settings.EMBEDDING_MODEL,
        }

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _format_sources(self, raw_sources: list[dict]) -> list[dict]:
        seen: dict[str, dict] = {}
        for s in raw_sources:
            url = s.get("url") or s.get("document_id", "")
            if url and url not in seen:
                seen[url] = {
                    "title":   s.get("title", "Untitled"),
                    "url":     s.get("url", ""),
                    "source":  s.get("source", ""),
                    "score":   round(s.get("score", 0), 3),
                    "snippet": s.get("content", "")[:150],
                }
        return list(seen.values())

    def _format_steps(self, steps) -> list[dict]:
        """Format ReAct steps cho UI — hiện trong thinking block."""
        return [
            {
                "iteration":   s.iteration,
                "thought":     s.thought,
                "action":      s.action,
                "action_input": s.action_input,
                "observation": s.observation[:300] if s.observation else "",
                "is_final":    s.is_final,
            }
            for s in steps
        ]

    async def _fetch_doc_meta(self, doc_ids: list[str]) -> dict[str, dict]:
        if not doc_ids:
            return {}
        rows = await self._repo.get_by_ids(doc_ids)
        return {r["id"]: r for r in rows}

    def _to_results(self, scored: list[dict], doc_meta: dict) -> list[SearchResult]:
        results = []
        for item in scored:
            doc_id = str(item.get("document_id", ""))
            meta   = doc_meta.get(doc_id, {})
            results.append(SearchResult(
                document_id=doc_id,
                chunk_id=str(item.get("chunk_id", "")),
                title=meta.get("title", "Unknown"),
                content=item.get("content", ""),
                url=meta.get("url", ""),
                source=meta.get("source", ""),
                author=meta.get("author", ""),
                score=item.get("final_score", 0.0),
                score_breakdown=item.get("score_breakdown", {}),
            ))
        return results