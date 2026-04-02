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
from typing import Any, List, Dict, Optional, Set, Tuple, cast

import httpx

from orchestration.tools import BaseTool, ToolResult
from retrieval.context_compressor import compress_context
from retrieval.semantic_cache import SemanticCache
from config.settings import settings
from llm.base import ILLMClient
from services.llm_service import LLMService
from prompts.agent_prompt import (
    SELF_CORRECT_SYSTEM,
    RELEVANCE_GRADE_SYSTEM,
    LOGIC_CHECK_SYSTEM,
    PLAN_SYSTEM,
    SUMMARIZE_SYSTEM,
)
from prompts.meeting_synthesis_prompt import MEETING_SYNTHESIS_SYSTEM

log = structlog.get_logger()

REACT_TIMEOUT = settings.AGENT_REACT_TIMEOUT

MAX_PLAN_STEPS = settings.AGENT_MAX_PLAN_STEPS

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
    used_edges: list[str] = field(default_factory=list)
    rewritten_query: str = ""


class ReActLoop:

    def __init__(self, tools: dict[str, BaseTool], max_iterations: int = 5, llm_client: ILLMClient = None, model_id: Optional[str] = None):

        self._tools = tools
        self._max_iterations = max_iterations
        self._cache = SemanticCache()

        if llm_client is None:
            self._llm = LLMService(model_id=model_id, task_type="agent")
        else:
            self._llm = llm_client

        log.info("tools.loaded", tools=list(self._tools.keys()))

    async def close(self):
        if hasattr(self._llm, "_client") and self._llm._managed_client:
            await self._llm._client.aclose()

    async def run(
        self,
        question: str,
        user_id: str = "",
        history: List[Dict] = None,
        on_thought: Any | None = None,
        on_token: Any | None = None,
        on_sources: Any | None = None,
    ) -> ReActResult:
        # 0. Checkpoint Initialization
        history = history or []
        log.info("agent.run", question=question[:100], history_len=len(history))
        
        # Summarize history if too long (Context Management)
        summarized_history = ""
        if history:
            history_text = "\n".join([f"{h.get('role')}: {h.get('content')}" for h in history])
            if len(history_text) > 3000:
                summarized_history = await self._summarize_history(history_text)
                log.info("agent.history.summarized", length=len(summarized_history))
            else:
                summarized_history = history_text
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

        query_understanding = await self._classify_query(question)
        need_graph = query_understanding.get("need_graph", False)
        log.info("agent.query_understanding", intent=query_understanding.get("intent"), need_graph=need_graph)

        # ─────────────────────────────
        # Planner (Skip for very simple questions)
        # ─────────────────────────────
        is_simple = len(question.strip()) < 40 and not any(kw in question.lower() for kw in [" và ", " and ", " sau đó ", " then ", " so sánh ", " compare "])
        
        if is_simple:
            log.info("agent.fast_path", reason="simple_query")
            plan = [PlanStep(step=1, tool="search_all", query=question, reason="Fast path direct search")]
        else:
            plan = await self._make_plan(question)

        log.info(
            "planner.plan",
            steps=[f"{str(p.query or '')}"[:30] for p in cast(List[PlanStep], plan)],
        )
        
        if on_thought:
            try:
                await on_thought({
                    "step": "planning",
                    "plan": [p.__dict__ for p in plan],
                    "thought": f"Tôi đã lập kế hoạch với {len(plan)} bước tìm kiếm." if not is_simple else "Tôi sẽ tìm kiếm trực tiếp cho câu hỏi này."
                })
            except Exception:
                pass

        sources: list[dict] = []
        source_urls: set[str] = set()
        used_tools: list[str] = []
        executed: list[ExecutedStep] = []
        graph_rels: set[str] = set()

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
                    graph_rels,
                    need_graph=need_graph,
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
                
                # Checkpoint: Progress update after each tool
                log.info("agent.checkpoint.tool", step=p.step, tool="search_all", status="done")
                
                if on_thought:
                    try:
                        await on_thought({
                            "step": "tool_execution",
                            "index": p.step,
                            "tool": "search_all",
                            "query": p.query,
                            "thought": f"Đang thực hiện tìm kiếm cho: {p.query[:50]}..."
                        })
                    except Exception:
                        pass

        # ─────────────────────────────
        # Early Exit: if we have very strong results already, skip rerank/retry/logic
        scores = [float(s.get("score") or 0) for s in cast(List[dict], sources)[:4]]
        best_initial = max(scores) if scores else 0.0
        
        if best_initial > 1.8:
            log.info("agent.early_exit", score=best_initial)
        else:
            retry_query: str | None = None
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
                    graph_rels,
                    need_graph=need_graph,
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
            log.info("context.compressed", sources=len(sources), context_chars=len(compressed_context))
        except Exception as e:
            log.warning("context_compressor.failed", error=str(e))
            compressed_context = ""

        # ─────────────────────────────────────────────────────────────
        # LAYER 1 — No-Answer Gate
        # Nếu tất cả sources đều có score thấp → không hỏi LLM
        # Tránh LLM "sáng tạo" câu trả lời khi không có dữ liệu tốt.
        # ─────────────────────────────────────────────────────────────
        no_answer_threshold = float(getattr(settings, "AGENT_NO_ANSWER_THRESHOLD", 0.35))
        final_scores = [float(s.get("agent_score") or s.get("score") or 0) for s in cast(List[dict], sources)[:6]]
        best_final = max(final_scores) if final_scores else 0.0

        if not sources or best_final < no_answer_threshold:
            log.info("agent.no_answer_gate", best_score=best_final, threshold=no_answer_threshold)
            vni_chars_gate = re.compile(r'[àáảãạăầấẩẫậắẳẵặêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', re.IGNORECASE)
            no_ans = (
                "Không tìm thấy thông tin liên quan trong kho tài liệu cho câu hỏi này."
                if bool(vni_chars_gate.search(question))
                else "No relevant information found in the knowledge base for this question."
            )
            return ReActResult(
                answer=no_ans,
                plan=plan,
                steps=[],
                sources=[],
                used_tools=list(set(used_tools)),
                rewritten_query=retry_query or question,
            )

        # ─────────────────────────────
        # LLM Summarize with Language Detection
        # ─────────────────────────────

        # Simple language detection (Vietnamese vs English)
        vni_chars = re.compile(r'[àáảãạăầấẩẫậắẳẵặêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', re.IGNORECASE)
        is_vietnamese = bool(vni_chars.search(question))
        target_lang = "Vietnamese" if is_vietnamese else "English"

        log.info("agent.language_detected", language=target_lang)

        if on_thought:
            try:
                await on_thought({
                    "step": "summarizing",
                    "thought": f"Đang tổng hợp thông tin bằng {target_lang} từ các nguồn tìm được..."
                })
            except Exception:
                pass

        # ─────────────────────────────────────────────────────────────
        # LAYER 2 — Citation Enforcement
        # Inject [SRC-N] markers vào context, instruct LLM cite chúng.
        # Sau khi LLM trả lời, parse cited IDs → verify → filter sources.
        # ─────────────────────────────────────────────────────────────
        cited_context, src_index = self._build_cited_context(
            sources=sources,
            compressed=compressed_context,
            graph_rels=graph_rels,
        )

        answer = await self._summarize(question, cited_context, target_language=target_lang, on_token=on_token, sources=sources)

        # Parse citations khỏi answer: [SRC-1], [SRC-2]...
        cited_ids: set[int] = set()
        for m in re.finditer(r'\[SRC-(\d+)\]', answer or ""):
            try:
                cited_ids.add(int(m.group(1)))
            except ValueError:
                pass

        # Nếu LLM có dùng SRC markers, chỉ giữ lại sources được cite
        if cited_ids and src_index:
            cited_sources = [src_index[i] for i in sorted(cited_ids) if i in src_index]
            if cited_sources:  # fallback: nếu filter quá aggressive, giữ nguyên
                sources = cited_sources
            log.info("agent.citations.parsed", cited=len(cited_ids), total_sources=len(src_index))

        # ─────────────────────────────────────────────────────────────
        # LAYER 3 — Coverage Check (không cần LLM call thêm)
        # Kiểm tra overlap giữa answer và top source content.
        # Nếu answer không có bất kỳ phrase nào từ sources → low_grounding.
        # ─────────────────────────────────────────────────────────────
        grounding_ok = self._check_coverage(answer, sources)
        if not grounding_ok:
            log.warning("agent.grounding.low", question=question[:80])
            # Append disclaimer thay vì block — không làm gián đoạn UX
            disclaimer = (
                "\n\n> ⚠️ *Lưu ý: Câu trả lời này có thể không hoàn toàn dựa trên tài liệu. Vui lòng kiểm tra nguồn.*"
                if is_vietnamese
                else "\n\n> ⚠️ *Note: This answer may not be fully grounded in the retrieved documents. Please verify the sources.*"
            )
            answer = (answer or "").rstrip() + disclaimer

        # ─────────────────────────────
        # Logic Agent: contradiction check (off by default — tốn latency)
        # Bật bằng AGENT_LOGIC_CHECK_ENABLED=true trong .env nếu cần
        # ─────────────────────────────
        try:
            should_logic = (
                getattr(settings, "AGENT_LOGIC_CHECK_ENABLED", False)  # default OFF
                and best_initial <= 2.5
                and len(sources) >= 3
                and len(question.strip()) > 30
            )
            if should_logic and compressed_context:
                logic = await self._logic_check(question, compressed_context)
                contradictions = logic.get("contradictions") or []
                confidence = logic.get("confidence")
                if contradictions:
                    lines = ["\n\n### Lưu ý (mâu thuẫn/khác biệt giữa nguồn)"]
                    for c in cast(List[dict], contradictions)[:4]:
                        point = str(c.get("point") or "").strip()
                        srcs = c.get("sources") or []
                        srcs_txt = ", ".join([str(s) for s in srcs if s]) if isinstance(srcs, list) else ""
                        if point:
                            lines.append(f"- {point}" + (f" (Sources: {srcs_txt})" if srcs_txt else ""))
                    answer = (answer or "").rstrip() + "\n".join(lines)
                if isinstance(confidence, (int, float)):
                    answer = (answer or "").rstrip() + f"\n\nĐộ tin cậy ước tính: {float(confidence or 0):.2f}"
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
                observation=str(e.observation or "")[:800],
            )
            for e in executed
        ]

        return ReActResult(
            answer=answer,
            plan=plan,
            steps=react_steps,
            sources=sources,
            used_tools=list(set(used_tools)),
            used_edges=list(set(graph_rels)),
            rewritten_query=retry_query or question,
        )

    def _should_retry(self, question: str, sources: list[dict]) -> bool:
        if not sources:
            return True
        scores = [float(s.get("agent_score") or s.get("score") or 0) for s in cast(List[dict], sources)[:6]]
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
                for i, s in enumerate(cast(List[dict], top))
            ]
        )
        out = await self._llm.chat(
            SELF_CORRECT_SYSTEM,
            f"Cau hoi: {question}\n\nTop ket qua hien tai:\n{obs}\n\nHay viet lai query de tim dung hon:",
            max_tokens=100,
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
        candidates = sources[:4] # Reduced from 8 to 4 for speed
        items = []
        for i, s in enumerate(candidates):
            title = str(s.get("title") or "Untitled")
            content = str(s.get("content") or "")
            items.append(f"[{i}] {title}\n{content[:800]}")

        prompt = (
            f'Cau hoi: "{question}"\n\n'
            f"Cham diem {len(items)} doan sau:\n\n"
            + "\n\n".join(items)
        )

        out = await self._llm.chat(RELEVANCE_GRADE_SYSTEM, prompt, max_tokens=150)
        out = re.sub(r"```(?:json)?|```", "", out).strip()
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return sources

        try:
            data = json.loads(m.group(0))
        except Exception:
            return sources

        grades = {}
        for g in (data.get("grades") or []):
            if not isinstance(g, dict):
                continue
            idx = g.get("i")
            score = g.get("score")
            if idx is not None and score is not None:
                try:
                    grades[int(idx)] = float(score)
                except (ValueError, TypeError):
                    continue

        for i, s in enumerate(candidates):
            g = grades.get(i, None)
            if g is None:
                continue
            g = max(0.0, min(float(g), 3.0))
            # Use a safe way to update dict to avoid lint errors if possible
            s.update({"agent_score": g})
            try:
                current_score = float(s.get("score") or 0)
                s.update({"score": max(current_score, float(g))})
            except Exception:
                s.update({"score": float(g)})

        reranked = sorted(sources, key=lambda x: float(x.get("agent_score") or x.get("score") or 0), reverse=True)
        return reranked

    async def _logic_check(self, question: str, context: str) -> dict:
        out = await self._llm.chat(
            LOGIC_CHECK_SYSTEM,
            f"Cau hoi: {question}\n\nCONTEXT:\n{str(context or '')[:8000]}",
            max_tokens=200,
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

    async def _classify_query(self, question: str) -> dict:
        sys_prompt = """
Bạn là Classifier cho hệ thống AI của doanh nghiệp. Bạn phải phân loại câu hỏi của người dùng để quyết định chiến lược tìm kiếm.
Trả về định dạng JSON DUY NHẤT: {"intent": "fact | flow | dependency | debugging | general", "entities": ["..."], "need_graph": true/false}

QUY TẮC "need_graph":
- true KHUYẾN CÁO: NẾU câu hỏi về các quy trình nghiệp vụ (flow), sự phụ thuộc hệ thống (dependency), kiến trúc tổng thể, hoặc luồng đi của dữ liệu.
- false KHUYẾN CÁO: NẾU câu hỏi tra cứu định nghĩa, fact chung chung, hỏi về nhân sự, dò dẫm lỗi (debugging) một đoạn log/code cụ thể.
"""
        import json
        try:
            raw = await self._llm.chat(sys_prompt, question, max_tokens=150)
            import re
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            return {"need_graph": False, "intent": "general"}
        except Exception:
            return {"need_graph": False, "intent": "general"}

    async def _make_plan(self, question: str) -> list[PlanStep]:

        try:

            out = await self._llm.chat(
                PLAN_SYSTEM,
                f"Câu hỏi: {question}",
                max_tokens=150,
            )

            out = re.sub(r"```json|```", "", out).strip()

            m = re.search(r"\{.*\}", out, re.DOTALL)

            if not m:
                raise ValueError("Planner output invalid")

            data = json.loads(m.group(0))

            steps = []

            for p in data.get("plan", [])[:MAX_PLAN_STEPS]:
                if isinstance(p, dict) and "step" in p:
                    steps.append(
                        PlanStep(
                            step=int(p["step"]),
                            tool="search_all",
                            query=str(p.get("query") or question),
                            reason=str(p.get("reason") or ""),
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
        graph_rels: set,
        need_graph: bool = False,
    ) -> str:

        if tool_name not in self._tools:
            return f"Tool '{tool_name}' không tồn tại."

        tool = self._tools[tool_name]

        try:
            import inspect
            sig = inspect.signature(tool.run)
            kwargs = {"query": query, "user_id": user_id}
            if "need_graph" in sig.parameters:
                kwargs["need_graph"] = need_graph

            result: ToolResult = await asyncio.wait_for(
                tool.run(**kwargs),
                timeout=300,
            )

            if result.success:
                if result.data and isinstance(result.data, list):
                    for r in result.data:
                        url = r.get("url")
                        if url and url not in source_urls:
                            sources.append(r)
                            source_urls.add(url)
                
                if result.graph_data:
                    graph_rels.update(result.graph_data)

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

    def _build_cited_context(
        self, 
        sources: list[dict], 
        compressed: str = "", 
        graph_rels: set[str] | None = None
    ) -> tuple[str, dict[int, dict]]:
        """
        LAYER 2: Build context with [SRC-N] markers.
        Returns (context_string, source_index_map).
        """
        src_index = {}
        lines = []
        
        # Nếu có compressed context, ta vẫn dùng nó nhưng bọc trong markers nếu có thể.
        # Ở đây đơn giản nhất là dùng raw sources (hoặc top N sources) để đảm bảo citation chính xác.
        # Nếu dùng compressed, ta coi đó là [SRC-1..N] gộp lại.
        
        for i, s in enumerate(sources[:15], 1):  # Limit to top 15 for context window
            src_index[i] = s
            title = s.get("title") or "Untitled"
            content = s.get("content") or ""
            lines.append(f"### [SRC-{i}] SOURCE: {title}\n{content}\n")
            
        context_txt = "\n".join(lines)
        
        if graph_rels:
            graph_context = "\n### KNOWLEDGE GRAPH (Use for relationships)\n" + "\n".join([f"- {rel}" for rel in sorted(graph_rels)])
            context_txt += graph_context
            
        return context_txt, src_index

    def _check_coverage(self, answer: str | None, sources: list[dict]) -> bool:
        """
        LAYER 3: Simple word-level overlap check.
        Checks if the answer contains at least some unique keywords/phrases from top sources.
        """
        if not answer or not sources:
            return True # Cannot check
            
        # Normalize and tokenize answer
        def tokenize(text: str):
            # Very simple tokenizer: lowercase and split by non-alphanumeric
            return set(re.findall(r'\w{4,}', text.lower())) # Only 4+ char words
            
        answer_tokens = tokenize(answer)
        if len(answer_tokens) < 5: # Too short to check reliably
            return True
            
        source_text = " ".join([s.get("content", "") for s in sources[:3]])
        source_tokens = tokenize(source_text)
        
        if not source_tokens:
            return True
            
        # Check intersection
        overlap = answer_tokens.intersection(source_tokens)
        
        # If less than 10% of answer words match source (and it's not a "no info" answer)
        # we flag it.
        no_info_phrases = ["không tìm thấy", "không đề cập", "không có thông tin", "no info", "does not mention"]
        answer_lower = answer.lower()
        if any(p in answer_lower for p in no_info_phrases):
            return True
            
        coverage_ratio = len(overlap) / len(answer_tokens)
        return coverage_ratio > 0.15 # 15% threshold for basic grounding

    async def _summarize_history(self, history_text: str) -> str:
        """Point 3: History Summarization to save tokens."""
        prompt = f"Đây là lịch sử hội thoại trước đó. Hãy tóm tắt ngắn gọn các ý chính và thông tin quan trọng để tôi có thể hiểu ngữ cảnh:\n\n{history_text}"
        try:
            summary = await self._llm.chat(SUMMARIZE_SYSTEM, prompt, max_tokens=250)
            return summary or history_text
        except Exception as e:
            log.warning("agent.history_summarize.failed", error=str(e))
            return history_text

    async def _summarize(self, question: str, context: str, target_language: str = "Vietnamese", on_token: Any | None = None, sources: list[dict] = None) -> str:
 
        if not context.strip():
            return "Không tìm thấy dữ liệu liên quan." if target_language == "Vietnamese" else "No relevant data found."
 
        prompt = f"""
QUESTION:
{question}
 
CONTEXT:
{context}
 
TASK:
Answer the question based ONLY on the CONTEXT.
Your response MUST be in {target_language}. 
If the question is in Vietnamese, you MUST answer in Vietnamese even if the context is in English.
"""

        try:
            # Switch to meeting synthesis prompt if applicable
            system_prompt = SUMMARIZE_SYSTEM
            if sources and self._is_meeting_synthesis_query(question, sources):
                system_prompt = MEETING_SYNTHESIS_SYSTEM
                log.info("agent.mode.meeting_synthesis")

            result = await self._llm.chat(
                system_prompt,
                prompt,
                max_tokens=4096,
                on_token=on_token,
            )

            if not result:
                return "Không có câu trả lời."

            return result

        except Exception as e:

            log.error("summarizer.failed", error=str(e))

            return "Không thể tổng hợp kết quả."

    def _is_meeting_synthesis_query(self, question: str, sources: list[dict]) -> bool:
        """
        Detect if the user wants to synthesize information across multiple meetings.
        Criteria:
        1. Context has at least 2 meeting sources (Zoom/Google Meet).
        2. Query contains synthesis keywords.
        """
        meeting_keywords = ["tổng hợp", "hợp nhất", "tất cả", "chuỗi", "meeting", "cuộc họp", "buổi họp", "synthesis", "aggregate", "consolidate"]
        q_lower = question.lower()
        has_keyword = any(kw in q_lower for kw in meeting_keywords)
        
        meeting_sources = [s for s in sources if str(s.get("source") or "").lower() in ("zoom", "google_meet")]
        has_meetings = len(meeting_sources) >= 1 # Even 1 meeting can benefit from the specialized prompt structure
        
        return has_keyword and has_meetings


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
