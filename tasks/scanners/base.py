from __future__ import annotations

import abc
import json
import re
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from llm.base import ILLMClient
from tasks.repository import TaskDraftRepository

log = structlog.get_logger()
_epic_re = re.compile(r"\b([A-Z][A-Z0-9]{1,10}-\d+)\b")


class BaseScanner(abc.ABC):
    """Abstract base class for source-specific task scanners."""

    def __init__(self, session: AsyncSession, repo: TaskDraftRepository, http_client, llm_client: ILLMClient):
        self.session = session
        self.repo = repo
        self.http_client = http_client
        self.llm_client = llm_client

    @abc.abstractmethod
    async def scan(self, days_back: int, triggered_by: str, created_by: str | None) -> int:
        """Scans the source and creates task drafts. Returns number of tasks created."""
        raise NotImplementedError

    async def _load_connector_selection(self, connector: str) -> dict:
        try:
            result = await self.session.execute(
                text("SELECT selection FROM connector_configs WHERE connector = :c"),
                {"c": connector},
            )
            raw = result.scalar()
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                return json.loads(raw) if raw else {}
        except Exception as e:
            log.error("scanner.load_selection.failed", connector=connector, error=str(e))
            pass

        # Multi-instance fallback
        try:
            inst = await self.session.execute(
                text("SELECT id::text FROM connector_instances WHERE connector_type = :t ORDER BY created_at ASC LIMIT 1"),
                {"t": connector},
            )
            instance_id = inst.scalar()
            if instance_id:
                connector_key = f"{connector}:{instance_id}"
                return await self._load_connector_selection(connector_key)
        except Exception as e:
            log.error("scanner.load_selection_fallback.failed", connector=connector, error=str(e))
            pass
        return {}

    def _csv_values(self, value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _detect_epic_key(self, text: str) -> str | None:
        text = str(text or "")
        return m.group(1) if "epic" in text.lower() and (m := _epic_re.search(text)) else None

    def _suggest_issue_type_from_labels(self, labels: list[str] | None) -> str:
        lower_labels = {str(x).lower() for x in (labels or [])}
        if "bug" in lower_labels: return "Bug"
        if "feature" in lower_labels: return "Story"
        return "Task"