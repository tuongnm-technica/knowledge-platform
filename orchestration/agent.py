"""
Agent — On-Premise RAG Pipeline
─────────────────────────────────
Full pipeline (no external API calls):
  User query
    → Query rewrite  (Ollama local LLM)
    → Permission filter  (PostgreSQL ACL)
    → Hybrid search  (Qdrant vector + PG full-text)
    → Ranking  (multi-signal scorer)
    → LLM answer  (Ollama local LLM)
    → Return answer + citations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from models.query import SearchQuery, SearchResult
from retrieval.hybrid.hybrid_search import HybridSearch
from permissions.filter import PermissionFilter
from ranking.scorer import RankingScorer
from persistence.document_repository import DocumentRepository
from prompts.rewrite_prompt import REWRITE_SYSTEM, REWRITE_USER_TEMPLATE
from prompts.answer_prompt import ANSWER_SYSTEM, ANSWER_USER_TEMPLATE
from config.settings import settings
from utils.text_utils import truncate
import httpx
import json
import structlog

log = structlog.get_logger()


class OllamaLLM:
    """
    Thin async wrapper around Ollama REST API (local).
    Ollama runs on the same AI Server — no external network needed.

    Install models: ollama pull llama3
    """

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
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,   # low temp for factual Q&A
            },
        }
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            try:
                resp = await client.post(f"{self._base}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"].strip()
            except httpx.TimeoutException:
                log.error("ollama.timeout", model=self._model)
                raise RuntimeError(f"Ollama LLM timed out after {settings.LLM_TIMEOUT}s. "
                                   "Consider using a smaller model or increasing LLM_TIMEOUT.")
            except httpx.HTTPStatusError as e:
                log.error("ollama.http_error", status=e.response.status_code)
                raise RuntimeError(f"Ollama returned error {e.response.status_code}: {e.response.text}")

    async def is_available(self) -> bool:
        """Health check — verify Ollama is running."""
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
        self._llm = OllamaLLM()

    # ─── Public entry points ─────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search without LLM answer — returns ranked document chunks."""
        allowed_ids = await self._permissions.allowed_docs(query.user_id)
        raw = await self._search.search(
            query.effective,
            top_k=query.limit,
            allowed_document_ids=allowed_ids,
        )

        doc_ids = list({str(r["document_id"]) for r in raw})
        doc_meta = await self._fetch_doc_meta(doc_ids)
        scored = self._scorer.score(raw, doc_meta)
        return self._to_results(scored, doc_meta)

    async def ask(self, question: str, user_id: str) -> dict:
        """
        Full on-premise RAG:
          rewrite (Ollama) → search (Qdrant+PG) → rank → answer (Ollama)
        Returns: {answer, sources, rewritten_query}
        """
        # 1. Rewrite query with local LLM
        rewritten = await self._rewrite_query(question)
        log.info("agent.rewrite", original=question[:80], rewritten=rewritten[:80])

        # 2. Retrieve & permission-filter
        query = SearchQuery(
            raw=question, rewritten=rewritten,
            user_id=user_id, limit=settings.TOP_K,
        )
        results = await self.search(query)

        if not results:
            return {
                "answer": "Không tìm thấy thông tin liên quan trong hệ thống knowledge base.",
                "sources": [],
                "rewritten_query": rewritten,
            }

        # 3. Build context (top 8 ranked chunks)
        context = self._build_context(results[:8])

        # 4. Generate answer with local Ollama
        answer = await self._generate_answer(question, context)

        # 5. Build sources — deduplicate theo url, thêm snippet
        sources = self._build_sources(results[:8])

        return {"answer": answer, "sources": sources, "rewritten_query": rewritten}

    async def health(self) -> dict:
        """Check all on-premise components."""
        ollama_ok = await self._llm.is_available()
        return {
            "ollama": "ok" if ollama_ok else "unavailable",
            "ollama_model": settings.OLLAMA_LLM_MODEL,
            "ollama_url": settings.OLLAMA_BASE_URL,
            "embedding_model": settings.EMBEDDING_MODEL,
        }

    # ─── Internal helpers ────────────────────────────────────────────────────

    async def _rewrite_query(self, question: str) -> str:
        prompt = REWRITE_USER_TEMPLATE.format(question=question)
        try:
            return await self._llm.chat(REWRITE_SYSTEM, prompt, max_tokens=150)
        except Exception as e:
            log.warning("agent.rewrite.failed", error=str(e))
            return question   # fallback: use original query

    async def _generate_answer(self, question: str, context: str) -> str:
        prompt = ANSWER_USER_TEMPLATE.format(question=question, context=context)
        return await self._llm.chat(ANSWER_SYSTEM, prompt, max_tokens=800)

    async def _fetch_doc_meta(self, doc_ids: list[str]) -> dict[str, dict]:
        if not doc_ids:
            return {}
        rows = await self._repo.get_by_ids(doc_ids)
        return {r["id"]: r for r in rows}

    def _build_sources(self, results: list[SearchResult]) -> list[dict]:
        """
        Deduplicate theo url + thêm snippet 150 chars.
        Ưu tiên chunk có score cao nhất cho mỗi url.
        """
        seen: dict[str, dict] = {}  # url → source dict

        for r in results:
            url = r.url or r.document_id  # fallback nếu url trống
            if url not in seen:
                # Tạo snippet từ content — 150 chars đầu có nghĩa
                snippet = self._make_snippet(r.content, max_len=150)
                seen[url] = {
                    "title":   r.title,
                    "url":     r.url,
                    "source":  r.source,
                    "score":   round(r.score, 3),
                    "snippet": snippet,
                }

        return list(seen.values())

    def _make_snippet(self, content: str, max_len: int = 150) -> str:
        """Lấy đoạn có nghĩa đầu tiên từ content, tối đa max_len chars."""
        if not content:
            return ""
        # Bỏ header dạng "=== #channel | date ===" nếu có
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        for line in lines:
            if len(line) > 20 and not line.startswith("==="):
                snippet = line[:max_len]
                return snippet + "..." if len(line) > max_len else snippet
        # Fallback: lấy thẳng từ đầu
        text = content.strip()[:max_len]
        return text + "..." if len(content) > max_len else text

    def _build_context(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] Title: {r.title}\n"
                f"Source: {r.url}\n"
                f"Content: {truncate(r.content, 600)}"
            )
        return "\n\n---\n\n".join(parts)

    def _to_results(self, scored: list[dict], doc_meta: dict[str, dict]) -> list[SearchResult]:
        results = []
        for item in scored:
            doc_id = str(item.get("document_id", ""))
            meta = doc_meta.get(doc_id, {})
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