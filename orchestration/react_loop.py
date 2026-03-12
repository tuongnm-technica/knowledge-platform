"""
orchestration/react_loop.py
ReAct loop với Planning step:
  1. PLAN   — LLM lập kế hoạch trước (danh sách bước)
  2. LOOP   — Thought → Action → Observation (lặp đến 5 lần)
  3. ANSWER — Tổng hợp câu trả lời
"""
from __future__ import annotations
import json
import re
import structlog
from dataclasses import dataclass, field
from orchestration.tools import BaseTool, ToolResult, build_tool_registry, tools_prompt_block
from config.settings import settings
import httpx

log = structlog.get_logger()

MAX_ITERATIONS = 5
REACT_TIMEOUT  = 600

# ─── Prompts ──────────────────────────────────────────────────────────────────

PLAN_SYSTEM = """\
Bạn là AI assistant nội bộ của Technica. Nhiệm vụ: lập kế hoạch tìm kiếm thông tin.

Các nguồn dữ liệu có sẵn:
- Confluence: tài liệu kỹ thuật, specs, quy trình, API docs
- Jira: bugs, tasks, issues, sprint
- Slack: thảo luận, quyết định, meeting notes trong chat
- File Server: báo cáo Word/Excel/PDF

Yêu cầu:
- Phân tích câu hỏi và lập plan ngắn gọn (2-4 bước)
- Mỗi bước ghi rõ: tên tool sẽ dùng + lý do
- Trả về ĐÚNG format JSON, không thêm text thừa

Format:
{
  "plan": [
    {"step": 1, "tool": "search_jira", "reason": "tìm bug liên quan"},
    {"step": 2, "tool": "search_slack", "reason": "tìm discussion về bug này"},
    {"step": 3, "tool": "search_confluence", "reason": "tìm context kỹ thuật"}
  ]
}"""

REACT_SYSTEM = """\
Bạn là AI assistant nội bộ của Technica. Thực hiện kế hoạch đã lập để trả lời câu hỏi.

Tools có sẵn:
{tools_block}

Kế hoạch đã lập:
{plan_text}

QUY TẮC BẮT BUỘC:
1. Thực hiện TỪNG BƯỚC theo plan — không được bỏ qua bước
2. Mỗi lần chỉ gọi 1 tool
3. Sau khi có đủ thông tin từ các bước trong plan → mới được FinalAnswer
4. ⚠️ TUYỆT ĐỐI KHÔNG bịa thông tin — chỉ dùng data từ Observation
5. ⚠️ Nếu tool trả về ERROR → thử query khác, KHÔNG tự bịa kết quả
6. ⚠️ Nếu tool trả về "Không tìm thấy" → ghi nhận và chuyển bước tiếp theo
7. Trả lời bằng tiếng Việt

Format CHÍNH XÁC (không được sai):

Thought: <suy nghĩ — đang ở bước nào, cần làm gì>
Action: <tên tool chính xác>
ActionInput: {{"key": "value"}}

Hoặc khi đã đủ thông tin:

Thought: <tóm tắt những gì đã tìm được>
FinalAnswer: <câu trả lời đầy đủ, có dẫn nguồn>
"""

REACT_CONTINUE = """\
Câu hỏi: {question}

Lịch sử:
{history}

Tiếp tục thực hiện bước tiếp theo trong plan. Nếu đã hoàn thành tất cả bước → FinalAnswer.
"""


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    step:   int
    tool:   str
    reason: str


@dataclass
class ReActStep:
    iteration:    int
    thought:      str
    action:       str = ""
    action_input: dict = field(default_factory=dict)
    observation:  str = ""
    is_final:     bool = False
    final_answer: str = ""


@dataclass
class ReActResult:
    answer:     str
    plan:       list[PlanStep]
    steps:      list[ReActStep]
    sources:    list[dict] = field(default_factory=list)
    used_tools: list[str]  = field(default_factory=list)


# ─── Main loop ────────────────────────────────────────────────────────────────

class ReActLoop:
    def __init__(self, tools: dict[str, BaseTool]):
        self._tools = tools
        self._base  = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

    async def run(self, question: str, user_id: str = "") -> ReActResult:
        # ── Phase 1: Planning ──
        plan = await self._make_plan(question)
        log.info("react.plan", steps=[f"{p.tool}" for p in plan])

        plan_text = "\n".join(
            f"  Bước {p.step}: {p.tool} — {p.reason}" for p in plan
        )

        # ── Phase 2: ReAct loop ──
        system_prompt = REACT_SYSTEM.format(
            tools_block=tools_prompt_block(self._tools),
            plan_text=plan_text,
        )

        steps:      list[ReActStep] = []
        sources:    list[dict]      = []
        used_tools: list[str]       = []
        history = ""

        for i in range(1, MAX_ITERATIONS + 1):
            log.info("react.iteration", i=i, plan_steps=len(plan))

            user_prompt = REACT_CONTINUE.format(question=question, history=history or "(Chưa có)")
            llm_out     = await self._call_llm(system_prompt, user_prompt)
            log.debug("react.llm_out", i=i, out=llm_out[:150])

            step = _parse_output(llm_out, i)
            steps.append(step)

            if step.is_final:
                log.info("react.done", iterations=i)
                return ReActResult(
                    answer=step.final_answer,
                    plan=plan, steps=steps,
                    sources=sources,
                    used_tools=list(set(used_tools)),
                )

            # Gọi tool
            obs = await self._call_tool(step, user_id, sources, used_tools)
            step.observation = obs

            history += (
                f"\n--- Bước {i} ---\n"
                f"Thought: {step.thought}\n"
                f"Action: {step.action}\n"
                f"ActionInput: {json.dumps(step.action_input, ensure_ascii=False)}\n"
                f"Observation: {obs[:600]}\n"
            )

        # Quá max iterations
        log.warning("react.max_iter", question=question[:60])
        fallback = await self._fallback(question, history)
        return ReActResult(
            answer=fallback, plan=plan, steps=steps,
            sources=sources, used_tools=list(set(used_tools)),
        )

    async def _make_plan(self, question: str) -> list[PlanStep]:
        """Phase 1: LLM lập kế hoạch trước khi execute."""
        try:
            out = await self._call_llm(
                PLAN_SYSTEM,
                f"Câu hỏi: {question}\n\nLập plan:",
                max_tokens=300,
            )
            # Strip markdown nếu có
            out = re.sub(r"```json|```", "", out).strip()
            # Tìm JSON object
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                return [
                    PlanStep(step=p["step"], tool=p["tool"], reason=p.get("reason", ""))
                    for p in data.get("plan", [])
                ]
        except Exception as e:
            log.warning("react.plan.failed", error=str(e))

        # Fallback plan nếu LLM không sinh đúng format
        return [PlanStep(step=1, tool="search_all", reason="tìm kiếm tổng hợp")]

    async def _call_tool(self, step: ReActStep, user_id: str,
                          sources: list, used_tools: list) -> str:
        if not step.action or step.action not in self._tools:
            return f"Tool '{step.action}' không tồn tại. Các tool hợp lệ: {list(self._tools.keys())}"

        tool   = self._tools[step.action]
        params = {**step.action_input, "user_id": user_id}
        result: ToolResult = await tool.run(**params)

        # Collect sources từ search tools
        if result.success and isinstance(result.data, list):
            for r in result.data:
                if isinstance(r, dict) and r.get("url"):
                    if r["url"] not in {s.get("url") for s in sources}:
                        sources.append(r)

        used_tools.append(step.action)
        log.info("react.tool", tool=step.action, ok=result.success)
        return result.to_observation()

    async def _call_llm(self, system: str, user: str, max_tokens: int = 600) -> str:
        payload = {
            "model":    self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream":  False,
            "options": {"num_predict": max_tokens, "temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=REACT_TIMEOUT) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

    async def _fallback(self, question: str, history: str) -> str:
        prompt = (
            f"Câu hỏi: {question}\n\n"
            f"Thông tin đã thu thập:\n{history}\n\n"
            "Tổng hợp câu trả lời tốt nhất dựa trên thông tin trên. "
            "Nếu thông tin không đủ, hãy nói rõ phần nào tìm được, phần nào không."
        )
        try:
            return await self._call_llm(
                "Bạn là AI assistant. Tổng hợp và trả lời bằng tiếng Việt.",
                prompt, max_tokens=800,
            )
        except Exception:
            return "Xin lỗi, không thể tổng hợp câu trả lời sau nhiều bước tìm kiếm."


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_output(text: str, iteration: int) -> ReActStep:
    # Strip DeepSeek thinking tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # FinalAnswer
    m = re.search(
        r"(?:FinalAnswer|Final Answer|Câu trả lời):\s*(.+)",
        text, re.DOTALL | re.IGNORECASE,
    )
    if m:
        thought_m = re.search(r"Thought:\s*(.+?)(?=\n(?:Action|FinalAnswer|Final))", text, re.DOTALL)
        return ReActStep(
            iteration=iteration,
            thought=thought_m.group(1).strip() if thought_m else "Đã đủ thông tin",
            is_final=True,
            final_answer=m.group(1).strip(),
        )

    # Thought
    thought_m = re.search(r"Thought:\s*(.+?)(?=\nAction|\Z)", text, re.DOTALL)
    thought   = thought_m.group(1).strip() if thought_m else text[:200]

    # Action
    action_m = re.search(r"Action:\s*(\w+)", text)
    action   = action_m.group(1).strip() if action_m else ""

    # ActionInput JSON
    action_input = {}
    input_m = re.search(r"ActionInput:\s*(\{.+?\})", text, re.DOTALL)
    if input_m:
        try:
            action_input = json.loads(input_m.group(1))
        except json.JSONDecodeError:
            raw = input_m.group(1)
            for k, v in re.findall(r'"(\w+)":\s*"([^"]*)"', raw):
                action_input[k] = v
            for k, v in re.findall(r'"(\w+)":\s*(\d+)', raw):
                action_input[k] = int(v)

    if not action:
        return ReActStep(iteration=iteration, thought=thought,
                         is_final=True, final_answer=text)

    return ReActStep(iteration=iteration, thought=thought,
                     action=action, action_input=action_input)