"""
tasks/repository.py
DB operations cho ai_task_drafts table.
"""
from __future__ import annotations
from datetime import datetime

import uuid
import hashlib
import json
import structlog
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from tasks.models import AITaskDraftORM, TaskDraftOut

log = structlog.get_logger()


class TaskDraftRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── Create ──────────────────────────────────────────────────────────────

    async def create_draft(
        self,
        title: str,
        description: str,
        source_type: str,           # slack | confluence
        source_ref: str,
        source_summary: str,
        source_url: str | None = None,
        source_meta: dict | None = None,
        evidence: list[dict] | None = None,
        issue_type: str = "Task",   # Task | Story | Bug | Epic
        epic_key: str | None = None,
        suggested_assignee: str | None = None,
        priority: str = "Medium",
        labels: list[str] | None = None,
        components: list[str] | None = None,
        due_date: str | None = None,  # YYYY-MM-DD
        suggested_fields: dict | None = None,
        triggered_by: str = "scheduler",
        created_by: str | None = None,
        jira_project: str | None = None,
        scope_group_id: str | None = None,
    ) -> str | None:
        """Tạo 1 draft task. Trả về id."""
        normalized = "|".join(
            [
                (source_type or "").strip().lower(),
                (source_ref or "").strip().lower(),
                (title or "").strip().lower(),
                (description or "").strip().lower()[:220],
            ]
        )
        dedup_key = hashlib.sha1(normalized.encode("utf-8")).hexdigest()

        # Dedup: skip nếu giống hệt nội dung từ cùng nguồn trong 7 ngày gần nhất (pending/confirmed).
        existing = await self._session.execute(text("""
            SELECT id FROM ai_task_drafts
            WHERE dedup_key = :dedup_key
              AND status IN ('pending', 'confirmed')
              AND created_at > NOW() - INTERVAL '7 days'
            LIMIT 1
        """), {"dedup_key": dedup_key})
        if existing.fetchone():
            log.debug("task_draft.skipped_duplicate", title=title[:50])
            return None

        draft_id = str(uuid.uuid4())
        await self._session.execute(text("""
            INSERT INTO ai_task_drafts
                (id, title, description, source_type, source_ref, source_summary, source_url, source_meta, evidence, suggested_fields, dedup_key,
                 issue_type, epic_key,
                 suggested_assignee, priority, labels, components, due_date, status, triggered_by,
                 created_by, jira_project, scope_group_id, created_at)
            VALUES
                (:id, :title, :description, :source_type, :source_ref, :source_summary, :source_url, CAST(:source_meta AS JSON), CAST(:evidence AS JSON), CAST(:suggested_fields AS JSON), :dedup_key,
                 :issue_type, :epic_key,
                 :suggested_assignee, :priority, :labels, :components, :due_date, 'pending', :triggered_by,
                 :created_by, :jira_project, :scope_group_id, NOW())
        """), {
            "id": draft_id, "title": title, "description": description,
            "source_type": source_type, "source_ref": source_ref,
            "source_summary": source_summary[:500] if source_summary else "",
            "source_url": (source_url or "").strip() or None,
            "source_meta": json.dumps(source_meta or {}),
            "evidence": json.dumps(evidence or []),
            "suggested_fields": json.dumps(suggested_fields or {}),
            "dedup_key": dedup_key,
            "issue_type": (issue_type or "Task").strip() or "Task",
            "epic_key": (epic_key or "").strip() or None,
            "suggested_assignee": suggested_assignee,
            "priority": priority,
            "labels": labels or [],
            "components": components or [],
            "due_date": (due_date or "").strip() or None,
            "triggered_by": triggered_by,
            "created_by": created_by,
            # jira_project is NOT NULL in DB; only allow NULL if the schema is changed accordingly.
            "jira_project": (jira_project or settings.DEFAULT_JIRA_PROJECT or "").strip() or "ECOS2025",
            "scope_group_id": (scope_group_id or "").strip() or None,
        })
        await self._session.commit()
        log.info("task_draft.created", id=draft_id, title=title[:50])
        return draft_id

    # ─── Read ─────────────────────────────────────────────────────────────────

    async def get_open(self) -> list[dict]:
        """Lấy tất cả draft đang pending/confirmed (chưa submit)."""
        stmt = (
            select(AITaskDraftORM)
            .where(AITaskDraftORM.status.in_(["pending", "confirmed"]))
            .order_by(AITaskDraftORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [dict(r) for r in result.mappings().all()]

    async def get_by_status(self, statuses: list[str]) -> list[dict]:
        """
        Fetch drafts by a list of statuses.
        Used for: include_submitted in UI, and future task history views.
        """
        statuses = [str(s).strip() for s in (statuses or []) if str(s).strip()]
        if not statuses:
            return []
        stmt = (
            select(AITaskDraftORM)
            .where(AITaskDraftORM.status.in_(statuses))
            .order_by(AITaskDraftORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [dict(r) for r in result.mappings().all()]

    async def get_by_id(self, draft_id: str) -> dict | None:
        result = await self._session.execute(text("""
            SELECT * FROM ai_task_drafts WHERE id = :id
        """), {"id": draft_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def count_pending(self) -> int:
        stmt = select(func.count()).select_from(AITaskDraftORM).where(
            AITaskDraftORM.status.in_(['pending', 'confirmed'])
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # ─── Update ───────────────────────────────────────────────────────────────

    async def confirm(
        self, draft_id: str, user_id: str,
        updates: dict | None = None,
    ) -> bool:
        """User confirm/edit draft. Draft remains in inbox (pending/confirmed)."""
        set_clauses = ["status = 'confirmed'"]
        params: dict = {"id": draft_id, "user_id": user_id}

        # Apply user edits nếu có
        if updates:
            for field in ("title", "description", "suggested_assignee", "priority", "jira_project", "due_date", "issue_type", "epic_key"):
                if field in updates and updates[field] is not None:
                    set_clauses.append(f"{field} = :{field}")
                    params[field] = updates[field]
            if "labels" in updates and updates["labels"] is not None:
                set_clauses.append("labels = :labels")
                params["labels"] = updates["labels"]
            if "components" in updates and updates["components"] is not None:
                set_clauses.append("components = :components")
                params["components"] = updates["components"]

        # Only set confirmer metadata on first confirmation.
        sql = f"""
            UPDATE ai_task_drafts
            SET {', '.join(set_clauses)},
                confirmed_by = COALESCE(confirmed_by, :user_id),
                confirmed_at = COALESCE(confirmed_at, NOW())
            WHERE id = :id AND status IN ('pending', 'confirmed')
        """
        result = await self._session.execute(text(sql), params)
        await self._session.commit()
        return result.rowcount > 0

    async def update_fields(self, draft_id: str, updates: dict) -> bool:
        """
        Update fields on a draft without changing its status.
        Allowed statuses: pending/confirmed.
        """
        if not updates:
            return False

        set_clauses: list[str] = []
        params: dict = {"id": draft_id}

        for field in ("title", "description", "suggested_assignee", "priority", "jira_project", "due_date", "issue_type", "epic_key"):
            if field in updates and updates[field] is not None:
                set_clauses.append(f"{field} = :{field}")
                params[field] = updates[field]

        if "labels" in updates and updates["labels"] is not None:
            set_clauses.append("labels = :labels")
            params["labels"] = updates["labels"]

        if "components" in updates and updates["components"] is not None:
            set_clauses.append("components = :components")
            params["components"] = updates["components"]

        if not set_clauses:
            return False

        sql = f"""
            UPDATE ai_task_drafts
            SET {', '.join(set_clauses)}
            WHERE id = :id AND status IN ('pending', 'confirmed')
        """
        result = await self._session.execute(text(sql), params)
        await self._session.commit()
        return result.rowcount > 0

    async def reject(self, draft_id: str, user_id: str) -> bool:
        """User reject draft."""
        result = await self._session.execute(text("""
            UPDATE ai_task_drafts
            SET status = 'rejected', confirmed_by = :user_id, confirmed_at = NOW()
            WHERE id = :id AND status IN ('pending', 'confirmed')
        """), {"id": draft_id, "user_id": user_id})
        await self._session.commit()
        return result.rowcount > 0

    async def mark_submitted(self, draft_id: str, jira_key: str, jira_meta: dict | None = None) -> None:
        """
        Sau khi tạo Jira thật thành công.

        Best-effort: merge jira_meta into suggested_fields for later use (e.g., assignee accountId).
        """
        suggested_fields = {}
        if jira_meta:
            try:
                row = await self._session.execute(
                    text("SELECT suggested_fields FROM ai_task_drafts WHERE id = :id"),
                    {"id": draft_id},
                )
                raw = row.scalar()
                if isinstance(raw, dict):
                    suggested_fields = raw
                elif isinstance(raw, str):
                    try:
                        suggested_fields = json.loads(raw) if raw else {}
                    except Exception:
                        suggested_fields = {}
            except Exception:
                suggested_fields = {}

            if not isinstance(suggested_fields, dict):
                suggested_fields = {}
            for k, v in (jira_meta or {}).items():
                if v is None:
                    continue
                suggested_fields[str(k)] = v

        await self._session.execute(
            text(
                """
                UPDATE ai_task_drafts
                SET status = 'submitted',
                    jira_key = :jira_key,
                    submitted_at = NOW(),
                    suggested_fields = CASE WHEN :sf IS NULL THEN suggested_fields ELSE CAST(:sf AS JSON) END
                WHERE id = :id
                """
            ),
            {"id": draft_id, "jira_key": jira_key, "sf": (json.dumps(suggested_fields) if jira_meta else None)},
        )
        await self._session.commit()
        log.info("task_draft.submitted", id=draft_id, jira_key=jira_key)

    async def suggest_assignee_from_history(self, *, labels: list[str] | None = None, components: list[str] | None = None) -> str | None:
        """
        Smart assignee suggestion (MVP):
        Use past submitted/done drafts with overlapping labels/components as a hint.

        This is intentionally lightweight (no extra tables). It gets better as the team uses the system.
        """
        labels = [str(x).strip() for x in (labels or []) if str(x).strip()]
        components = [str(x).strip() for x in (components or []) if str(x).strip()]
        if not labels and not components:
            return None

        try:
            result = await self._session.execute(
                text(
                    """
                    SELECT suggested_assignee, COUNT(*) AS c
                    FROM ai_task_drafts
                    WHERE status IN ('submitted', 'done')
                      AND suggested_assignee IS NOT NULL
                      AND suggested_assignee <> ''
                      AND (
                        (:labels::TEXT[] IS NOT NULL AND labels && CAST(:labels AS TEXT[]))
                        OR (:components::TEXT[] IS NOT NULL AND components && CAST(:components AS TEXT[]))
                      )
                      AND created_at > NOW() - INTERVAL '180 days'
                    GROUP BY suggested_assignee
                    ORDER BY c DESC
                    LIMIT 1
                    """
                ),
                {
                    "labels": labels if labels else None,
                    "components": components if components else None,
                },
            )
            row = result.mappings().first()
            if not row:
                return None
            value = str(row.get("suggested_assignee") or "").strip()
            return value or None
        except Exception:
            return None
