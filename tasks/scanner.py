from __future__ import annotations

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from services.llm_service import LLMService

from config.settings import settings
from tasks.repository import TaskDraftRepository
from .scanner_registry import SCANNERS


log = structlog.get_logger()


async def scan_and_create_drafts(
    session: AsyncSession,
    triggered_by: str = "scheduler",
    created_by: str | None = None,
    slack_days: int = 1,
    confluence_days: int = 1,
) -> dict:
    """
    Main entry point for scanning various sources to generate task drafts.
    Delegates to specific scanner strategies defined in SCANNERS.
    """
    repo = TaskDraftRepository(session)
    stats = {"total": 0, "errors": []}
    days_map = {"slack": slack_days, "confluence": confluence_days}

    # A single HTTP client is shared for both LLM calls and other API calls.
    async with httpx.AsyncClient(timeout=60) as http_client:
        llm_client = LLMService(
            model=settings.OLLAMA_LLM_MODEL,
        )

        for source, scanner_cls in SCANNERS.items():
            scanner = scanner_cls(session, repo, http_client, llm_client)
            days_back = days_map.get(source, 1)
            try:
                tasks_found = await scanner.scan(days_back, triggered_by, created_by)
                stats[f"{source}_tasks"] = tasks_found
                stats["total"] += tasks_found
            except Exception as exc:
                log.error(f"scanner.{source}.error", error=str(exc), exc_info=True)
                stats["errors"].append(f"{source.capitalize()}: {exc}")
                stats[f"{source}_tasks"] = 0

    log.info("scanner.done", **{k: v for k, v in stats.items() if k != "errors"})
    return stats
