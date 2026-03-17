"""
orchestration/react_loop.py
Planner + Executor architecture
(Context Compression + Semantic Cache)
"""

from __future__ import annotations

import asyncio
import json
import re
import structlog
from dataclasses import dataclass, field

import httpx

from orchestration.tools import BaseTool, ToolResult
from retrieval.context_compressor import compress_context
from retrieval.semantic_cache import SemanticCache
from config.settings import settings
from llm.base import ILLMClient
from llm.ollama import OllamaLLMClient
from prompts.agent_prompt import (
    SELF_CORRECT_SYSTEM,
    RELEVANCE_GRADE_SYSTEM,
    LOGIC_CHECK_SYSTEM,
    PLAN_SYSTEM,
    SUMMARIZE_SYSTEM,
)

log = structlog.get_logger()

REACT_TIMEOUT = 600

MAX_PLAN_STEPS = 3

@dataclass
class PlanStep:
    step: int
    tool: str
    query: str
    reason: str = ""
    parallel: bool = False


@dataclass
class ExecutedStep:
    step: int
    tool: str
    query: str
    observation: str
    success: bool = True


@dataclass
class ReActStep:
    iteration: int
    thought: str
    action: str = ""
    action_input: dict = field(default_factory=dict)
    observation: str = ""
    is_final: bool = False
    final_answer: str = ""


@dataclass
class ReActResult:
    answer: str
    plan: list[PlanStep]
    steps: list[ReActStep]
    sources: list[dict] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)
    rewritten_query: str = ""


class ReActLoop:

    def __init__(self, tools: dict[str, BaseTool], max_iterations: int = 5, llm_client: ILLMClient = None):

        self._tools = tools
        self._max_iterations = max_iterations
        self._cache = SemanticCache()

        if llm_client is None:
            self._llm = OllamaLLMClient(
                base_url=settings.OLLAMA_BASE_URL, 
                model=settings.OLLAMA_LLM_MODEL,
                timeout=REACT_TIMEOUT
            )
        else:
            self._llm = llm_client

        log.info("tools.loaded", tools=list(self._tools.keys()))

    async def close(self):
        if hasattr(self._llm, "_client") and self._llm._managed_client:
            await self._llm._client.aclose()

    async def run(self, question: str, user_id: str = "") -> ReActResult:
        # Fast path: semantic cache
        if settings.SEMANTIC_CACHE_ENABLED:
            try:
                cached = await self._cache.lookup(question)
                if cached:
                    return ReActResult(
                        answer=cached,
                        plan=[],
                        steps=[
                            ReActStep(
                                iteration=0,
                                thought="Semantic cache hit",
                                action="semantic_cache",
                                action_input={"query": question},
                                observation="cached_answer",
                                is_final=True,
                                final_answer=cached,
                            )
                        ],
                        sources=[],
                        used_tools=["semantic_cache"],
                        rewritten_query=question,
                    )
            except Exception as e:
                log.warning("semantic_cache.lookup_failed", error=str(e))

        # ─────────────────────────────
        # Planner
        # ─────────────────────────────

        plan = await self._make_plan(question)

        log.info(
            "planner.plan",
            steps=[f"{p.query[:30]}" for p in plan],
        )

        sources: list[dict] = []
        source_urls: set[str] = set()
        used_tools: list[str] = []
        executed: list[ExecutedStep] = []

        groups = _group_parallel(plan)

        for group in groups:

            tasks = [
                self._run_tool(
                    "search_all",  # luôn dùng search_all
                    p.query,
                    user_id,
                    sources,
                    source_urls,
                    used_tools,
                )
                for p in group
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for p, obs in zip(group, results):

                if isinstance(obs, Exception):
                    obs = "Tool execution failed"

                executed.append(
                    ExecutedStep(
                        step=p.step,
                        tool="search_all",
                        query=p.query,
                        observation=str(obs),
                    )
                )

        # ─────────────────────────────
        # Self-correction & reranking (Search Agent + Critic)
        # ─────────────────────────────
        retry_query = None
        try:
            if getattr(settings, "AGENT_SELF_CORRECT_ENABLED", True):
                sources = await self._grade_and_rerank(question, sources)
                if self._should_retry(question, sources):
                    retry_query = await self._rewrite_query(question, sources)
        except Exception as e:
            log.warning("agent.self_correct.failed", error=str(e))

        if retry_query:
            try:
                await self._run_tool(
                    "search_all",
                    retry_query,
                    user_id,
                    sources,
                    source_urls,
                    used_tools,
                )
                executed.append(
                    ExecutedStep(
                        step=len(executed) + 1,
                        tool="search_all",
                        query=retry_query,
                        observation="Self-correction retry search executed",
                    )
                )
                sources = await self._grade_and_rerank(question, sources)
                log.info("agent.self_correct.retried", query=retry_query[:120], sources=len(sources))
            except Exception as e:
                log.warning("agent.self_correct.retry_failed", error=str(e))

        # ─────────────────────────────
        # Context Compression
        # ─────────────────────────────

        try:

            compressed_context = compress_context(sources)

            log.info(
                "context.compressed",
                sources=len(sources),
                context_chars=len(compressed_context),
            )

        except Exception as e:

            log.warning("context_compressor.failed", error=str(e))
            compressed_context = ""

        # ─────────────────────────────
        # LLM Summarize
        # ─────────────────────────────

        answer = await self._summarize(question, compressed_context)

        # ─────────────────────────────
        # Logic Agent: contradiction check (best-effort)
        # ─────────────────────────────
        try:
            if getattr(settings, "AGENT_LOGIC_CHECK_ENABLED", True) and compressed_context:
                logic = await self._logic_check(question, compressed_context)
                contradictions = logic.get("contradictions") or []
                confidence = logic.get("confidence")
                if contradictions:
                    lines = ["\n\n### Luu y (mau thuan/khac biet giua nguon)"]
                    for c in contradictions[:4]:
                        point = str(c.get("point") or "").strip()
                        srcs = c.get("sources") or []
                        srcs_txt = ", ".join([str(s) for s in srcs if s]) if isinstance(srcs, list) else ""
                        if point:
                            lines.append(f"- {point}" + (f" (Sources: {srcs_txt})" if srcs_txt else ""))
                    if isinstance(confidence, (int, float)):
                        lines.append(f"\nDo tin cay uoc tinh: {round(float(confidence), 2)}")
                    answer = (answer or "").rstrip() + "\n" + "\n".join(lines)
        except Exception as e:
            log.warning("agent.logic_check.failed", error=str(e))

        # ─────────────────────────────
        # Store Semantic Cache
        # ─────────────────────────────

        if settings.SEMANTIC_CACHE_ENABLED:
            try:
                if answer and "Không tìm thấy dữ liệu" not in answer:
                    await self._cache.store(question, answer)
            except Exception as e:
                log.warning("semantic_cache.store_failed", error=str(e))

        react_steps = [
            ReActStep(
                iteration=e.step,
                thought=f"Bước {e.step}",
                action=e.tool,
                action_input={"query": e.query},
                observation=e.observation[:800],
            )
            for e in executed
        ]

        return ReActResult(
            answer=answer,
            plan=plan,
            steps=react_steps,
            sources=sources,
            used_tools=list(set(used_tools)),
            rewritten_query=retry_query or question,
        )

    def _should_retry(self, question: str, sources: list[dict]) -> bool:
        if not sources:
            return True
        scores = [float(s.get("agent_score") or s.get("score") or 0) for s in sources[:6]]
        best = max(scores) if scores else 0.0
        avg = sum(scores) / max(1, len(scores))
        # Heuristic: if even the best hit is weak, try once more.
        return best < 1.2 and avg < 1.1 and len(question.strip()) >= 8

    async def _rewrite_query(self, question: str, sources: list[dict]) -> str | None:
        # Provide short evidence of mismatch to the model.
        top = sources[:4]
        obs = "\n\n".join(
            [
                f"[{i}] {s.get('title','')}\n{str(s.get('content','') or '')[:260]}"
                for i, s in enumerate(top)
            ]
        )
        out = await self._llm.chat(
            SELF_CORRECT_SYSTEM,
            f"Cau hoi: {question}\n\nTop ket qua hien tai:\n{obs}\n\nHay viet lai query de tim dung hon:",
            max_tokens=120,
        )
        out = re.sub(r"```(?:json)?|```", "", out).strip()
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
            q = str(data.get("query") or "").strip()
            return q or None
        except Exception:
            return None

    async def _grade_and_rerank(self, question: str, sources: list[dict]) -> list[dict]:
        if not sources:
            return sources

        # Grade top sources only (cheap), keep rest as-is.
        candidates = sources[:8]
        items = []
        for i, s in enumerate(candidates):
            title = str(s.get("title") or "Untitled")
            content = str(s.get("content") or "")[:800]
            items.append(f"[{i}] {title}\n{content}")

        prompt = (
            f'Cau hoi: "{question}"\n\n'
            f"Cham diem {len(items)} doan sau:\n\n"
            + "\n\n".join(items)
        )

        out = await self._llm.chat(RELEVANCE_GRADE_SYSTEM, prompt, max_tokens=220)
        out = re.sub(r"```(?:json)?|```", "", out).strip()
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return sources

        try:
            data = json.loads(m.group(0))
        except Exception:
            return sources

        grades = {int(g.get("i")): float(g.get("score") or 0) for g in (data.get("grades") or []) if isinstance(g, dict)}

        for i, s in enumerate(candidates):
            g = grades.get(i, None)
            if g is None:
                continue
            g = max(0.0, min(float(g), 3.0))
            s["agent_score"] = g
            # Use the stronger score to help context_compressor filtering.
            try:
                s["score"] = max(float(s.get("score") or 0), g)
            except Exception:
                s["score"] = g

        reranked = sorted(sources, key=lambda x: float(x.get("agent_score") or x.get("score") or 0), reverse=True)
        return reranked

    async def _logic_check(self, question: str, context: str) -> dict:
        out = await self._llm.chat(
            LOGIC_CHECK_SYSTEM,
            f"Cau hoi: {question}\n\nCONTEXT:\n{context[:8000]}",
            max_tokens=260,
        )
        out = re.sub(r"```(?:json)?|```", "", out).strip()
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return {"contradictions": [], "confidence": 0.5}
        try:
            data = json.loads(m.group(0))
            if not isinstance(data, dict):
                return {"contradictions": [], "confidence": 0.5}
            return data
        except Exception:
            return {"contradictions": [], "confidence": 0.5}

    async def _make_plan(self, question: str) -> list[PlanStep]:

        try:

            out = await self._llm.chat(
                PLAN_SYSTEM,
                f"Câu hỏi: {question}",
                max_tokens=200,
            )

            out = re.sub(r"```json|```", "", out).strip()

            m = re.search(r"\{.*\}", out, re.DOTALL)

            if not m:
                raise ValueError("Planner output invalid")

            data = json.loads(m.group(0))

            steps = []

            for p in data.get("plan", [])[:MAX_PLAN_STEPS]:

                steps.append(
                    PlanStep(
                        step=p["step"],
                        tool="search_all",
                        query=p.get("query", question),
                        reason=p.get("reason", ""),
                        parallel=bool(p.get("parallel", False)),
                    )
                )

            if steps:
                return steps

        except Exception as e:
            log.warning("planner.failed", error=str(e))

        return [PlanStep(step=1, tool="search_all", query=question)]

    async def _run_tool(
        self,
        tool_name: str,
        query: str,
        user_id: str,
        sources: list,
        source_urls: set,
        used_tools: list,
    ) -> str:

        if tool_name not in self._tools:
            return f"Tool '{tool_name}' không tồn tại."

        tool = self._tools[tool_name]

        try:

            result: ToolResult = await asyncio.wait_for(
                tool.run(query=query, user_id=user_id),
                timeout=300,
            )

            if result.success and isinstance(result.data, list):

                for r in result.data:

                    url = r.get("url")

                    if url and url not in source_urls:
                        sources.append(r)
                        source_urls.add(url)

            used_tools.append(tool_name)

            return result.to_observation()

        except Exception as e:

            import traceback

            log.error(
                "executor.tool.error",
                tool=tool_name,
                error=str(e),
                traceback=traceback.format_exc(),
            )

            return "Tool execution error"

    async def _summarize(self, question: str, context: str) -> str:

        if not context.strip():
            return "Không tìm thấy dữ liệu liên quan."

        prompt = f"""
QUESTION:
{question}

CONTEXT:
{context}

Trả lời câu hỏi dựa trên CONTEXT.
"""

        try:

            result = await self._llm.chat(
                SUMMARIZE_SYSTEM,
                prompt,
                max_tokens=400,
            )

            if not result:
                return "Không có câu trả lời."

            return result

        except Exception as e:

            log.error("summarizer.failed", error=str(e))

            return "Không thể tổng hợp kết quả."


def _group_parallel(plan: list[PlanStep]) -> list[list[PlanStep]]:

    groups = []
    current = []

    for p in plan:

        if not p.parallel:

            if current:
                groups.append(current)
                current = []

            groups.append([p])

        else:
            current.append(p)

    if current:
        groups.append(current)

    return groups
