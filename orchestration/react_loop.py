"""
orchestration/react_loop.py

Planner + Executor architecture:
  1. PLAN      — LLM lập kế hoạch (danh sách tool + query)
  2. EXECUTE   — Orchestrator code chạy từng bước, LLM KHÔNG được skip
  3. SUMMARIZE — LLM tổng hợp từ tất cả observations

LLM không kiểm soát loop — code kiểm soát.
"""
from __future__ import annotations
import asyncio
import json
import re
import structlog
from dataclasses import dataclass, field
from orchestration.tools import BaseTool, ToolResult, build_tool_registry, tools_prompt_block
from config.settings import settings
import httpx

log = structlog.get_logger()

REACT_TIMEOUT = 600

# ─── Prompts ──────────────────────────────────────────────────────────────────

PLAN_SYSTEM = """\
# ROLE
Bạn là AI Dispatcher chiến lược của Technica, chuyên trách lập kế hoạch truy vấn dữ liệu nội bộ.

# OBJECTIVE
Xây dựng lộ trình tìm kiếm đồng bộ trên 3 nền tảng (Confluence, Slack, Jira) để thu thập thông tin toàn diện về một sự kiện hoặc yêu cầu nghiệp vụ.

# QUERY EXPANSION STRATEGY (BẮT BUỘC)
- **Xử lý ngày tháng:** Nếu query có ngày (vd: 9/2), phải tạo biến thể "DD/MM" (09/02) và "D/M" (9/2). 
- **Bổ trợ nội dung:** Luôn đính kèm từ khóa nghiệp vụ (Ecor, ATRS, Auction, SRS, Back Order) thay vì chỉ để ngày tháng đơn độc.
- **Đa dạng hóa:** Chuyển đổi từ khóa ngắn (<3 từ) thành các cụm từ mô tả hành động (vd: "meeting note", "logic thanh lý", "API integration").

# OUTPUT FORMAT (JSON ONLY)
{
  "plan": [
    {
      "step": 1,
      "tool": "search_confluence",
      "query": "<Từ khóa chính + Biến thể ngày tháng>",
      "reason": "Truy xuất tài liệu đặc tả (SRS) và biên bản họp chính thức.",
      "parallel": false
    },
    {
      "step": 2,
      "tool": "search_slack",
      "query": "<Từ khóa nghiệp vụ + Nội dung thảo luận>",
      "reason": "Tìm kiếm các quyết định thay đổi nhanh hoặc thảo luận chưa ghi lại trong tài liệu.",
      "parallel": true
    },
    {
      "step": 3,
      "tool": "search_jira",
      "query": "<Từ khóa nội dung + Trạng thái task>",
      "reason": "Kiểm tra tiến độ thực hiện và các issue phát sinh liên quan.",
      "parallel": true
    }
  ]
}

# CONTEXT EXAMPLES
- Input: "Meeting 9/2 Auction"
- Query Confluence: "9/2 09/02 Meeting note Auction"
- Query Slack: "Auction meeting 9/2 discussion"
- Query Jira: "Auction module task 9/2"
"""

SUMMARIZE_SYSTEM = """\
# ROLE
Bạn là Senior Business Analyst (BA) tại Technica, có khả năng đọc hiểu sâu sắc các tài liệu kỹ thuật và biên bản họp.

# TASK
Trích xuất và cấu trúc hóa các yêu cầu nghiệp vụ từ dữ liệu quan sát (Observations). Tuyệt đối không làm mất mát dữ liệu chi tiết.

# GUIDELINES & CONSTRAINTS
- **Độ chi tiết tối đa:** Nếu nguồn có danh sách (bullet points) về tính năng, thông số (model, giá, logic...), bạn PHẢI liệt kê 100% các điểm đó. Không được tóm tắt gộp thành câu văn xuôi.
- **Trọng tâm dữ liệu:** Đặc biệt chú ý thông tin trong ngoặc đơn `(...)` – đây thường là dữ liệu tham chiếu quan trọng nhất.
- **Bảo tồn thuật ngữ:** Giữ nguyên các thuật ngữ chuyên môn: Ecor, ATRS, Auction, Back Order, Module thanh lý, API, v.v.
- **Trung thực:** Chỉ trích xuất thông tin có trong văn bản, không tự ý suy diễn logic nếu không có căn cứ.

# OUTPUT STRUCTURE
---
### 1. BỐI CẢNH THẢO LUẬN
(Mô tả ngắn gọn: Ai họp? Khi nào? Về dự án nào?)

### 2. DANH SÁCH YÊU CẦU CHI TIẾT
(Sử dụng Bullet points. Phân loại theo: Tính năng | Logic nghiệp vụ | Thông số kỹ thuật)

### 3. NGUỒN TRÍCH DẪN & THAM CHIẾU
(Ghi rõ từ Confluence/Slack/Jira và ngày tháng liên quan)
---
"""


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    step:     int
    tool:     str
    query:    str          # query cụ thể cho tool này — do LLM sinh ra trong plan
    reason:   str = ""
    parallel: bool = False


@dataclass
class ExecutedStep:
    step:        int
    tool:        str
    query:       str
    observation: str
    success:     bool = True


@dataclass
class ReActStep:
    """Giữ lại để tương thích với ask.py response schema."""
    iteration:             int
    thought:               str
    action:                str  = ""
    action_input:          dict = field(default_factory=dict)
    observation:           str  = ""
    is_final:              bool = False
    final_answer:          str  = ""
    parallel_actions:      list = field(default_factory=list)
    parallel_observations: list = field(default_factory=list)


@dataclass
class ReActResult:
    answer:     str
    plan:       list[PlanStep]
    steps:      list[ReActStep]
    sources:    list[dict] = field(default_factory=list)
    used_tools: list[str]  = field(default_factory=list)


# ─── Main class ───────────────────────────────────────────────────────────────

class ReActLoop:
    def __init__(self, tools: dict[str, BaseTool], max_iterations: int = 5):
        self._tools         = tools
        self._max_iterations = max_iterations
        self._base  = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

    async def run(self, question: str, user_id: str = "") -> ReActResult:
        # ── Phase 1: LLM lập kế hoạch ────────────────────────────────────────
        plan = await self._make_plan(question)
        log.info("planner.plan", steps=[f"{p.tool}({p.query[:30]})" for p in plan])

        # ── Phase 2: Orchestrator thực thi từng bước ─────────────────────────
        # LLM KHÔNG kiểm soát loop — code kiểm soát
        sources:    list[dict] = []
        used_tools: list[str]  = []
        executed:   list[ExecutedStep] = []

        # Nhóm các bước parallel lại
        groups = _group_parallel(plan)

        for group in groups:
            if len(group) == 1:
                # Sequential
                p = group[0]
                obs = await self._run_tool(p.tool, p.query, user_id, sources, used_tools)
                executed.append(ExecutedStep(step=p.step, tool=p.tool, query=p.query, observation=obs))
                log.info("executor.step", step=p.step, tool=p.tool, chars=len(obs))
            else:
                # Parallel
                log.info("executor.parallel", count=len(group), tools=[p.tool for p in group])
                tasks = [self._run_tool(p.tool, p.query, user_id, sources, used_tools) for p in group]
                results = await asyncio.gather(*tasks)
                for p, obs in zip(group, results):
                    executed.append(ExecutedStep(step=p.step, tool=p.tool, query=p.query, observation=obs))
                    log.info("executor.parallel_step", step=p.step, tool=p.tool, chars=len(obs))

        # ── Phase 3: LLM tổng hợp từ TẤT CẢ observations ────────────────────
        obs_text = "\n\n".join(
            f"[Bước {e.step} — {e.tool}({e.query})]:\n{e.observation}"
            for e in sorted(executed, key=lambda x: x.step)
        )
        answer = await self._summarize(question, obs_text)

        # Convert sang ReActStep để tương thích response schema cũ
        react_steps = [
            ReActStep(
                iteration=e.step,
                thought=f"Bước {e.step}: {e.tool}",
                action=e.tool,
                action_input={"query": e.query},
                observation=e.observation[:2000],
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

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _make_plan(self, question: str) -> list[PlanStep]:
        try:
            out = await self._call_llm(
                PLAN_SYSTEM,
                f"Câu hỏi: {question}\n\nLập plan:",
                max_tokens=400,
            )
            out = re.sub(r"```json|```|<think>.*?</think>", "", out, flags=re.DOTALL).strip()
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                steps = []
                for p in data.get("plan", []):
                    steps.append(PlanStep(
                        step=p["step"],
                        tool=p.get("tool", "search_all"),
                        query=p.get("query", question),   # LLM cung cấp query cụ thể
                        reason=p.get("reason", ""),
                        parallel=bool(p.get("parallel", False)),
                    ))
                if steps:
                    return steps
        except Exception as e:
            log.warning("planner.failed", error=str(e))

        # Fallback: search_all với câu hỏi gốc
        return [PlanStep(step=1, tool="search_all", query=question, reason="fallback")]

    async def _run_tool(
        self,
        tool_name: str,
        query: str,
        user_id: str,
        sources: list,
        used_tools: list,
    ) -> str:
        if tool_name not in self._tools:
            return f"Tool '{tool_name}' không tồn tại."

        tool = self._tools[tool_name]
        params = {"query": query, "user_id": user_id}

        try:
            result: ToolResult = await tool.run(**params)

            # collect sources
            if result.success and isinstance(result.data, list):
                for r in result.data:
                    if isinstance(r, dict) and r.get("url"):
                        if r["url"] not in {s.get("url") for s in sources}:
                            sources.append(r)

            used_tools.append(tool_name)

            obs = result.to_observation()

            return f"""
            === SOURCE: {tool_name} ===
            QUERY: {query}

            RESULTS:
            {obs}

            ========================
            """
        
        except Exception as e:
            log.error("executor.tool.error", tool=tool_name, error=str(e))
            return f"Lỗi khi gọi {tool_name}: {str(e)}"

    async def _summarize(self, question: str, observations: str) -> str:
        # Guard: nếu observations quá ít thì trả lời sớm
        if not observations or len(observations.strip()) < 10:
            return "Tôi đã tìm kiếm nhưng không thấy dữ liệu liên quan trong Confluence, Slack và Jira."
        prompt = (
            f"CÂU HỎI NGƯỜI DÙNG: {question}\n\n"
            f"DỮ LIỆU TÌM ĐƯỢC (OBSERVATIONS):\n{observations}\n\n"
            "Hãy phân tích kỹ các thảo luận trong Slack và Jira và Confluence để trả lời."
        )
        try:
            return await self._call_llm(SUMMARIZE_SYSTEM, prompt, max_tokens=1000)
        except Exception as e:
            log.error("summarizer.failed", error=str(e))
            return f"Lỗi khi tổng hợp: {str(e)}"

    async def _call_tools_parallel(self, parallel_actions, user_id, sources, used_tools):
        """Chạy nhiều tools đồng thời bằng asyncio.gather()."""
        async def _run_one(pa):
            tool_name  = pa.get("action", "")
            tool_input = pa.get("input", {})
            query      = tool_input.get("query", "")
            return await self._run_tool_direct(tool_name, query, user_id, sources, used_tools)
        return list(await asyncio.gather(*[_run_one(pa) for pa in parallel_actions]))

    async def _run_tool_direct(
        self, tool_name: str, query: str,
        user_id: str, sources: list, used_tools: list,
    ) -> str:
        """Chạy tool trực tiếp với query — dùng bởi Executor, không qua LLM."""
        if tool_name not in self._tools:
            return f"Tool '{tool_name}' không tồn tại. Hợp lệ: {list(self._tools.keys())}"
        tool   = self._tools[tool_name]
        params = {"query": query, "user_id": user_id}
        try:
            result: ToolResult = await tool.run(**params)
            if result.success and isinstance(result.data, list):
                for r in result.data:
                    if isinstance(r, dict) and r.get("url"):
                        if r["url"] not in {s.get("url") for s in sources}:
                            sources.append(r)
            used_tools.append(tool_name)
            log.info("executor.tool", tool=tool_name, ok=result.success)
            return result.to_observation()
        except Exception as e:
            log.error("executor.tool.error", tool=tool_name, error=str(e))
            return f"Lỗi khi gọi {tool_name}: {str(e)}"

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
            out = resp.json()["message"]["content"].strip()
            # Strip DeepSeek thinking tags
            return re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()


# ─── Parallel grouping ────────────────────────────────────────────────────────

def _group_parallel(plan: list[PlanStep]) -> list[list[PlanStep]]:
    """
    Nhóm các bước parallel liền kề lại.
    Bước đầu tiên (parallel=false) luôn chạy riêng.
    Các bước parallel=true liên tiếp chạy cùng nhau.
    """
    if not plan:
        return []

    groups: list[list[PlanStep]] = []
    current_group: list[PlanStep] = []

    for p in plan:
        if not p.parallel:
            # Flush group hiện tại
            if current_group:
                groups.append(current_group)
                current_group = []
            groups.append([p])
        else:
            current_group.append(p)

    if current_group:
        groups.append(current_group)

    return groups


def _parse_output(text: str, iteration: int) -> "ReActStep":
    """Legacy parser — không dùng trong Executor flow nhưng giữ để tương thích."""
    import re, json
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return ReActStep(iteration=iteration, thought=text[:200], is_final=True, final_answer=text)