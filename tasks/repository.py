"""
tasks/repository.py
DB operations cho ai_task_drafts table.
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from tasks.models import TaskDraftOut
from datetime import datetime
import uuid
import structlog

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
        suggested_assignee: str | None = None,
        priority: str = "Medium",
        labels: list[str] | None = None,
        triggered_by: str = "scheduler",
        created_by: str | None = None,
        jira_project: str = "ECOS2025",
    ) -> str:
        """Tạo 1 draft task. Trả về id."""
        # Dedup: skip nếu title giống từ cùng source trong 24h
        existing = await self._session.execute(text("""
            SELECT id FROM ai_task_drafts
            WHERE source_ref = :source_ref
              AND title = :title
              AND status = 'pending'
              AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """), {"source_ref": source_ref, "title": title})
        if existing.fetchone():
            log.debug("task_draft.skipped_duplicate", title=title[:50])
            return None

        draft_id = str(uuid.uuid4())
        await self._session.execute(text("""
            INSERT INTO ai_task_drafts
                (id, title, description, source_type, source_ref, source_summary,
                 suggested_assignee, priority, labels, status, triggered_by,
                 created_by, jira_project, created_at)
            VALUES
                (:id, :title, :description, :source_type, :source_ref, :source_summary,
                 :suggested_assignee, :priority, :labels, 'pending', :triggered_by,
                 :created_by, :jira_project, NOW())
        """), {
            "id": draft_id, "title": title, "description": description,
            "source_type": source_type, "source_ref": source_ref,
            "source_summary": source_summary[:500] if source_summary else "",
            "suggested_assignee": suggested_assignee,
            "priority": priority,
            "labels": labels or [],
            "triggered_by": triggered_by,
            "created_by": created_by,
            "jira_project": jira_project,
        })
        await self._session.commit()
        log.info("task_draft.created", id=draft_id, title=title[:50])
        return draft_id

    # ─── Read ─────────────────────────────────────────────────────────────────

    async def get_pending(self) -> list[dict]:
        """Lấy tất cả draft đang pending."""
        result = await self._session.execute(text("""
            SELECT id, title, description, source_type, source_ref, source_summary,
                   suggested_assignee, priority, labels, status, triggered_by,
                   created_by, jira_key, jira_project, created_at
            FROM ai_task_drafts
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """))
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_by_id(self, draft_id: str) -> dict | None:
        result = await self._session.execute(text("""
            SELECT * FROM ai_task_drafts WHERE id = :id
        """), {"id": draft_id})
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def count_pending(self) -> int:
        result = await self._session.execute(text(
            "SELECT COUNT(*) FROM ai_task_drafts WHERE status = 'pending'"
        ))
        return result.scalar() or 0

    # ─── Update ───────────────────────────────────────────────────────────────

    async def confirm(
        self, draft_id: str, user_id: str,
        updates: dict | None = None,
    ) -> bool:
        """User confirm draft → status = confirmed."""
        set_clauses = [
            "status = 'confirmed'",
            "confirmed_by = :user_id",
            "confirmed_at = NOW()",
        ]
        params: dict = {"id": draft_id, "user_id": user_id}

        # Apply user edits nếu có
        if updates:
            for field in ("title", "description", "suggested_assignee", "priority", "jira_project"):
                if field in updates and updates[field] is not None:
                    set_clauses.append(f"{field} = :{field}")
                    params[field] = updates[field]

        sql = f"UPDATE ai_task_drafts SET {', '.join(set_clauses)} WHERE id = :id AND status = 'pending'"
        result = await self._session.execute(text(sql), params)
        await self._session.commit()
        return result.rowcount > 0

    async def reject(self, draft_id: str, user_id: str) -> bool:
        """User reject draft → xóa khỏi DB."""
        result = await self._session.execute(text("""
            UPDATE ai_task_drafts
            SET status = 'rejected', confirmed_by = :user_id, confirmed_at = NOW()
            WHERE id = :id AND status = 'pending'
        """), {"id": draft_id, "user_id": user_id})
        await self._session.commit()
        return result.rowcount > 0

    async def mark_submitted(self, draft_id: str, jira_key: str) -> None:
        """Sau khi tạo Jira thật thành công."""
        await self._session.execute(text("""
            UPDATE ai_task_drafts
            SET status = 'submitted', jira_key = :jira_key, submitted_at = NOW()
            WHERE id = :id
        """), {"id": draft_id, "jira_key": jira_key})
        await self._session.commit()
        log.info("task_draft.submitted", id=draft_id, jira_key=jira_key)