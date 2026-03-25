from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ExtractedReference:
    kind: str  # url|jira_key|unc_path
    value: str


class DocumentLinker:
    """
    Extract and persist explicit document-to-document links.

    Notes:
    - Links are best-effort (only stored when the target document exists in DB).
    - We keep link creation lightweight so it can run during ingestion.
    """

    URL_RE = re.compile(r"(https?://[^\s<>\"]+)", re.IGNORECASE)
    JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,10}-\d+)\b")
    UNC_RE = re.compile(r"(\\\\[A-Za-z0-9._-]+\\[^\s\"<>]+)")

    TRAILING_PUNCT = ".,;:)]}>\"'"

    def __init__(self, session: AsyncSession):
        self._session = session

    @classmethod
    def extract(cls, text_value: str) -> list[ExtractedReference]:
        value = str(text_value or "")
        if not value:
            return []

        refs: list[ExtractedReference] = []

        for url in cls.URL_RE.findall(value):
            cleaned = cls._clean_ref(url)
            if cleaned:
                refs.append(ExtractedReference(kind="url", value=cleaned))

        for unc in cls.UNC_RE.findall(value):
            cleaned = cls._clean_ref(unc)
            if cleaned:
                refs.append(ExtractedReference(kind="unc_path", value=cleaned))

        for key in cls.JIRA_KEY_RE.findall(value):
            cleaned = cls._clean_ref(key).upper()
            if cleaned:
                refs.append(ExtractedReference(kind="jira_key", value=cleaned))

        # Deduplicate while keeping a stable order.
        seen: set[tuple[str, str]] = set()
        unique: list[ExtractedReference] = []
        for ref in refs:
            k = (ref.kind, ref.value)
            if k in seen:
                continue
            seen.add(k)
            unique.append(ref)
        return unique

    @classmethod
    def _clean_ref(cls, value: str) -> str:
        v = str(value or "").strip()
        if not v:
            return ""
        v = v.strip(cls.TRAILING_PUNCT)
        return v

    async def upsert_for_document(self, source_document_id: str, content: str) -> dict:
        """
        Extract references from content and upsert rows in document_links.
        Returns stats for logging.
        """
        refs = self.extract(content)
        if not refs:
            return {"explicit_links": 0, "explicit_targets": 0}

        urls = sorted({r.value for r in refs if r.kind in {"url", "unc_path"} and r.value})
        jira_keys = sorted({r.value for r in refs if r.kind == "jira_key" and r.value})

        targets_by_url: dict[str, str] = {}
        targets_by_jira: dict[str, str] = {}

        if urls:
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text AS id, url
                        FROM documents
                        WHERE url = ANY(:urls)
                        """
                    ),
                    {"urls": urls},
                )
            ).mappings().all()
            targets_by_url = {str(r["url"]): str(r["id"]) for r in rows if r.get("url") and r.get("id")}

        if jira_keys:
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT id::text AS id, (metadata->>'issue_key') AS issue_key
                        FROM documents
                        WHERE source = 'jira'
                          AND (metadata->>'issue_key') = ANY(:keys)
                        """
                    ),
                    {"keys": jira_keys},
                )
            ).mappings().all()
            targets_by_jira = {str(r["issue_key"]): str(r["id"]) for r in rows if r.get("issue_key") and r.get("id")}

        target_ids: set[str] = set()
        for ref in refs:
            if ref.kind in {"url", "unc_path"}:
                doc_id = targets_by_url.get(ref.value)
            elif ref.kind == "jira_key":
                doc_id = targets_by_jira.get(ref.value)
            else:
                doc_id = None

            if not doc_id:
                continue
            if str(doc_id) == str(source_document_id):
                continue
            target_ids.add(str(doc_id))

        if not target_ids:
            return {"explicit_links": 0, "explicit_targets": 0}

        for target_id in sorted(target_ids):
            await self._session.execute(
                text(
                    """
                    INSERT INTO document_links
                      (id, source_document_id, target_document_id, kind, relation, weight, evidence, created_at)
                    VALUES
                      (:id, CAST(:src AS UUID), CAST(:dst AS UUID), 'explicit', 'references', 1.0, NULL, NOW())
                    ON CONFLICT (source_document_id, target_document_id, kind, relation)
                    DO UPDATE SET
                      weight = GREATEST(document_links.weight, EXCLUDED.weight)
                    """
                ),
                {"id": str(uuid.uuid4()), "src": source_document_id, "dst": target_id},
            )

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return {"explicit_links": len(target_ids), "explicit_targets": len(target_ids)}

