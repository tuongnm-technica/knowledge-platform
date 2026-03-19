"""
orchestration/tools/__init__.py
Tool registry — đăng ký tất cả tools.
"""
from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from orchestration.tools.search import (
    ConfluenceSearchTool, JiraSearchTool, SlackSearchTool,
    FileSearchTool, GlobalSearchTool,
)
from orchestration.tools.jira_tool import GetJiraIssueTool, ListJiraIssuesTool
from orchestration.tools.slack_tool import GetSlackMessagesTool
from orchestration.tools.summarize import SummarizeDocumentTool
from sqlalchemy.ext.asyncio import AsyncSession


def build_tool_registry(session: AsyncSession) -> dict[str, BaseTool]:
    tools = [
        # Search by source
        ConfluenceSearchTool(session),
        JiraSearchTool(session),
        SlackSearchTool(session),
        FileSearchTool(session),
        GlobalSearchTool(session),
        # Direct API tools
        GetJiraIssueTool(),
        ListJiraIssuesTool(),
        GetSlackMessagesTool(),
        # Utility
        SummarizeDocumentTool(session),
    ]
    return {t.spec.name: t for t in tools}


def tools_prompt_block(registry: dict[str, BaseTool]) -> str:
    blocks = [t.spec.to_prompt_block() for t in registry.values()]
    return "\n\n".join(blocks)


__all__ = ["BaseTool", "ToolSpec", "ToolResult", "build_tool_registry", "tools_prompt_block"]