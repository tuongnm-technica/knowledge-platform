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
import structlog

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
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

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
        self._llm = OllamaLLM()

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        allowed_ids = await self._permissions.allowed_docs(query.user_id)
        raw = await self._search.search(query.effective, top_k=query.limit, allowed_document_ids=allowed_ids)
        doc_ids = list({str(r["document_id"]) for r in raw})
        doc_meta = await self._fetch_doc_meta(doc_ids)
        scored = self._scorer.score(raw, doc_meta)
        return self._to_results(scored, doc_meta)

    async def ask(self, question: str, user_id: str) -> dict:
        rewritten = await self._rewrite_query(question)
        query = SearchQuery(raw=question, rewritten=rewritten, user_id=user_id, limit=settings.TOP_K)
        results = await self.search(query)

        if not results:
            return {
                "answer": "Không tìm thấy thông tin liên quan trong hệ thống knowledge base.",
                "sources": [],
                "rewritten_query": rewritten,
            }

        context = self._build_context(results[:5])
        answer = await self._generate_answer(question, context)
        sources = [{"title": r.title, "url": r.url, "source": r.source, "score": round(r.score, 3)} for r in results[:5]]
        return {"answer": answer, "sources": sources, "rewritten_query": rewritten}

    async def _rewrite_query(self, question: str) -> str:
        try:
            prompt = REWRITE_USER_TEMPLATE.format(question=question)
            return await self._llm.chat(REWRITE_SYSTEM, prompt, max_tokens=150)
        except Exception as e:
            log.warning("agent.rewrite.failed", error=str(e))
            return question

    async def _generate_answer(self, question: str, context: str) -> str:
        prompt = ANSWER_USER_TEMPLATE.format(question=question, context=context)
        return await self._llm.chat(ANSWER_SYSTEM, prompt, max_tokens=800)

    async def _fetch_doc_meta(self, doc_ids: list[str]) -> dict[str, dict]:
        if not doc_ids:
            return {}
        rows = await self._repo.get_by_ids(doc_ids)
        return {r["id"]: r for r in rows}

    def _build_context(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] Title: {r.title}\nSource: {r.url}\nContent: {truncate(r.content, 1500)}")
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