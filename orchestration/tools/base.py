"""
orchestration/tools/base.py
Base interface cho tất cả tools trong ReAct agent.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    data: Any                        # kết quả thực tế
    summary: str                     # 1-2 câu tóm tắt cho LLM đọc
    error: str = ""
    graph_data: list[str] = field(default_factory=list)

    def to_observation(self) -> str:
        """Format để đưa vào ReAct observation block."""
        if not self.success:
            return f"ERROR: {self.error}"
        return self.summary


@dataclass
class ToolSpec:
    name: str
    description: str                 # LLM đọc để biết khi nào dùng tool này
    parameters: dict = field(default_factory=dict)  # {param_name: description}

    def to_prompt_block(self) -> str:
        params = "\n".join(f"  - {k}: {v}" for k, v in self.parameters.items())
        return f"Tool: {self.name}\nMô tả: {self.description}\nParams:\n{params}"


class BaseTool(ABC):
    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        ...

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        ...