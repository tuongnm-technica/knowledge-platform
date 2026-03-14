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

log = structlog.get_logger()

REACT_TIMEOUT = 600
LLM_TIMEOUT = 120

MAX_PLAN_STEPS = 3



PLAN_SYSTEM = """
Bạn là AI Dispatcher chuyên lập kế hoạch tìm kiếm thông tin kỹ thuật.

QUY TẮC BẮT BUỘC:
1. Luôn giữ nguyên định dạng ngày/tháng dạng số (ví dụ: 9/2, 11/3) trong query. 
2. TUYỆT ĐỐI KHÔNG dịch ngày tháng sang chữ tiếng Anh (vd: Không dịch 9/2 thành February hay September).
3. Luôn lập kế hoạch bằng tiếng Việt.

Return ONLY valid JSON:
{
 "plan":[
  {
   "step":1,
   "query":"meeting note 9/2",
   "reason":"Tìm nội dung thảo luận ngày 9/2",
   "parallel":false
  }
 ]
}
"""



SUMMARIZE_SYSTEM = """
Bạn là Business Analyst.

Nhiệm vụ:
Trả lời câu hỏi dựa trên dữ liệu CONTEXT.

Quy tắc:

1. Chỉ sử dụng thông tin trong CONTEXT
2. Nếu có nhiều nguồn hãy tổng hợp
3. Nếu CONTEXT không đủ hãy nói rõ
4. Trích thông tin quan trọng

Trả lời rõ ràng và có cấu trúc.
"""


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


class ReActLoop:

    def __init__(self, tools: dict[str, BaseTool], max_iterations: int = 5):

        self._tools = tools
        self._max_iterations = max_iterations

        self._base = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

        self._cache = SemanticCache()

        self._client = httpx.AsyncClient(
            timeout=REACT_TIMEOUT,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

        log.info("tools.loaded", tools=list(self._tools.keys()))

    async def close(self):
        await self._client.aclose()

    async def run(self, question: str, user_id: str = "") -> ReActResult:

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
        # Store Semantic Cache
        # ─────────────────────────────

        # try:
        #     if answer and "Không tìm thấy dữ liệu" not in answer:
        #         await self._cache.store(question, answer)
        # except Exception as e:
        #     log.warning("semantic_cache.store_failed", error=str(e))

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
        )

    async def _make_plan(self, question: str) -> list[PlanStep]:

        try:

            out = await self._call_llm(
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

            result = await self._call_llm(
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

    async def _call_llm(self, system: str, user: str, max_tokens: int = 400) -> str:

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,
            },
        }

        resp = await self._client.post(
            f"{self._base}/api/chat",
            json=payload,
            timeout=LLM_TIMEOUT,
        )

        resp.raise_for_status()

        data = resp.json()

        msg = data.get("message", {})

        out = msg.get("content", "")

        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL)

        return out.strip()


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