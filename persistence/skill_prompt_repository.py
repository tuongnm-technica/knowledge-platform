from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prompts.doc_draft_prompt import (
    SKILL_AGENT_LABELS,
    SKILL_SYSTEM_PROMPTS,
    SUPPORTED_DOC_TYPES,
)


class SkillPromptRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── Read ─────────────────────────────────────────────────────────────────

    async def list_all(self) -> list[dict]:
        """Return all skill prompts ordered by doc_type."""
        result = await self._session.execute(
            text("""
                SELECT doc_type, label, description, system_prompt,
                       updated_at, updated_by
                FROM skill_prompts
                ORDER BY doc_type
            """)
        )
        return [dict(row) for row in result.mappings().all()]

    async def get(self, doc_type: str) -> dict | None:
        """Return a single skill prompt by doc_type."""
        result = await self._session.execute(
            text("""
                SELECT doc_type, label, description, system_prompt,
                       updated_at, updated_by
                FROM skill_prompts
                WHERE doc_type = :doc_type
            """),
            {"doc_type": doc_type},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    # ─── Write ────────────────────────────────────────────────────────────────

    async def upsert(
        self,
        *,
        doc_type: str,
        label: str,
        description: str,
        system_prompt: str,
        updated_by: str = "system",
    ) -> None:
        await self._session.execute(
            text("""
                INSERT INTO skill_prompts
                    (doc_type, label, description, system_prompt, updated_at, updated_by)
                VALUES
                    (:doc_type, :label, :description, :system_prompt, :updated_at, :updated_by)
                ON CONFLICT (doc_type)
                DO UPDATE SET
                    label         = EXCLUDED.label,
                    description   = EXCLUDED.description,
                    system_prompt = EXCLUDED.system_prompt,
                    updated_at    = EXCLUDED.updated_at,
                    updated_by    = EXCLUDED.updated_by
            """),
            {
                "doc_type": doc_type,
                "label": label,
                "description": description,
                "system_prompt": system_prompt,
                "updated_at": datetime.utcnow(),
                "updated_by": updated_by,
            },
        )
        await self._session.commit()

    async def update_prompt(
        self,
        *,
        doc_type: str,
        system_prompt: str,
        updated_by: str,
    ) -> bool:
        """Update only the system_prompt for an existing row. Returns True if found."""
        result = await self._session.execute(
            text("""
                UPDATE skill_prompts
                SET system_prompt = :system_prompt,
                    updated_at    = :updated_at,
                    updated_by    = :updated_by
                WHERE doc_type = :doc_type
                RETURNING doc_type
            """),
            {
                "doc_type": doc_type,
                "system_prompt": system_prompt,
                "updated_at": datetime.utcnow(),
                "updated_by": updated_by,
            },
        )
        await self._session.commit()
        return result.scalar() is not None

    async def reset_to_default(self, *, doc_type: str, updated_by: str) -> bool:
        """Reset system_prompt to the hardcoded default. Returns True if found."""
        default = SKILL_SYSTEM_PROMPTS.get(doc_type)
        if default is None:
            return False
        result = await self._session.execute(
            text("""
                UPDATE skill_prompts
                SET system_prompt = :system_prompt,
                    updated_at    = :updated_at,
                    updated_by    = :updated_by
                WHERE doc_type = :doc_type
                RETURNING doc_type
            """),
            {
                "doc_type": doc_type,
                "system_prompt": default,
                "updated_at": datetime.utcnow(),
                "updated_by": updated_by,
            },
        )
        await self._session.commit()
        return result.scalar() is not None

    # ─── Seeder ───────────────────────────────────────────────────────────────

    async def seed_defaults(self) -> int:
        """Populate skill_prompts from hardcoded defaults (INSERT IF NOT EXISTS). Returns rows inserted."""
        count = 0
        for doc_type, system_prompt in SKILL_SYSTEM_PROMPTS.items():
            label_tuple = SKILL_AGENT_LABELS.get(doc_type, ("", ""))
            label = label_tuple[0] if label_tuple else doc_type
            description = label_tuple[1] if label_tuple else ""
            result = await self._session.execute(
                text("""
                    INSERT INTO skill_prompts
                        (doc_type, label, description, system_prompt, updated_at, updated_by)
                    VALUES
                        (:doc_type, :label, :description, :system_prompt, :updated_at, 'system')
                    ON CONFLICT (doc_type) DO NOTHING
                    RETURNING doc_type
                """),
                {
                    "doc_type": doc_type,
                    "label": label,
                    "description": description,
                    "system_prompt": system_prompt,
                    "updated_at": datetime.utcnow(),
                },
            )
            if result.scalar():
                count += 1
        await self._session.commit()
        return count
