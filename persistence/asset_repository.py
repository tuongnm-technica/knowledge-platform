from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_asset(
        self,
        *,
        document_id: str,
        source: str,
        source_ref: str | None,
        kind: str,
        filename: str | None,
        mime_type: str | None,
        bytes_size: int | None,
        sha256: str | None,
        local_path: str,
        caption: str | None = None,
        ocr_text: str | None = None,
        width: int | None = None,
        height: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        asset_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Best-effort de-dup per document by sha256 if provided.
        if sha256:
            r = await self._session.execute(
                text(
                    """
                    SELECT id::text
                    FROM document_assets
                    WHERE document_id::text = :doc_id
                      AND sha256 = :sha
                    LIMIT 1
                    """
                ),
                {"doc_id": document_id, "sha": sha256},
            )
            existing = r.scalar()
            if existing:
                await self._session.execute(
                    text(
                        """
                        UPDATE document_assets
                        SET caption = COALESCE(:caption, caption),
                            ocr_text = COALESCE(:ocr_text, ocr_text),
                            meta = CASE
                                WHEN :meta::text IS NULL OR :meta::text = '' THEN meta
                                ELSE CAST(:meta AS JSON)
                            END
                        WHERE id::text = :id
                        """
                    ),
                    {"id": existing, "caption": caption, "ocr_text": ocr_text, "meta": json.dumps(meta or {})},
                )
                try:
                    await self._session.commit()
                except Exception:
                    await self._session.rollback()
                    raise
                return str(existing)

        await self._session.execute(
            text(
                """
                INSERT INTO document_assets
                (id, document_id, source, source_ref, kind, filename, mime_type, bytes, sha256,
                 local_path, caption, ocr_text, width, height, meta, created_at)
                VALUES
                (CAST(:id AS UUID), CAST(:document_id AS UUID), :source, :source_ref, :kind, :filename, :mime_type,
                 :bytes, :sha256, :local_path, :caption, :ocr_text, :width, :height, CAST(:meta AS JSON), :created_at)
                """
            ),
            {
                "id": asset_id,
                "document_id": document_id,
                "source": source,
                "source_ref": source_ref,
                "kind": kind,
                "filename": filename,
                "mime_type": mime_type,
                "bytes": int(bytes_size or 0) or None,
                "sha256": sha256,
                "local_path": local_path,
                "caption": caption,
                "ocr_text": ocr_text,
                "width": int(width) if width is not None else None,
                "height": int(height) if height is not None else None,
                "meta": json.dumps(meta or {}),
                "created_at": now,
            },
        )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return asset_id

    async def find_by_doc_sha256(self, *, document_id: str, sha256: str) -> dict[str, Any] | None:
        doc_id = str(document_id or "").strip()
        sha = str(sha256 or "").strip().lower()
        if not doc_id or not sha:
            return None
        r = await self._session.execute(
            text(
                """
                SELECT
                    id::text,
                    document_id::text AS document_id,
                    local_path,
                    mime_type,
                    filename,
                    caption
                FROM document_assets
                WHERE document_id::text = :doc_id
                  AND sha256 = :sha
                LIMIT 1
                """
            ),
            {"doc_id": doc_id, "sha": sha},
        )
        row = r.mappings().first()
        return dict(row) if row else None

    async def link_chunk_assets(self, *, chunk_id: str, asset_ids: list[str]) -> None:
        ids = [str(i or "").strip() for i in (asset_ids or []) if str(i or "").strip()]
        if not chunk_id or not ids:
            return
        for asset_id in sorted(set(ids)):
            await self._session.execute(
                text(
                    """
                    INSERT INTO chunk_assets (chunk_id, asset_id)
                    VALUES (CAST(:chunk_id AS UUID), CAST(:asset_id AS UUID))
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"chunk_id": chunk_id, "asset_id": asset_id},
            )
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        r = await self._session.execute(
            text(
                """
                SELECT
                    id::text,
                    document_id::text AS document_id,
                    source,
                    source_ref,
                    kind,
                    filename,
                    mime_type,
                    bytes,
                    sha256,
                    local_path,
                    caption,
                    ocr_text,
                    width,
                    height,
                    meta,
                    created_at
                FROM document_assets
                WHERE id::text = :id
                """
            ),
            {"id": str(asset_id or "").strip()},
        )
        row = r.mappings().first()
        return dict(row) if row else None

    async def assets_for_chunks(self, chunk_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        ids = [str(i or "").strip() for i in (chunk_ids or []) if str(i or "").strip()]
        if not ids:
            return {}
        r = await self._session.execute(
            text(
                """
                SELECT
                    ca.chunk_id::text AS chunk_id,
                    a.id::text        AS asset_id,
                    a.kind,
                    a.filename,
                    a.mime_type,
                    a.local_path,
                    a.caption
                FROM chunk_assets ca
                JOIN document_assets a ON a.id = ca.asset_id
                WHERE ca.chunk_id::text = ANY(:ids)
                ORDER BY ca.chunk_id, a.created_at ASC
                """
            ),
            {"ids": ids},
        )
        out: dict[str, list[dict[str, Any]]] = {}
        for row in r.mappings().all():
            cid = str(row.get("chunk_id") or "")
            out.setdefault(cid, []).append(
                {
                    "asset_id": str(row.get("asset_id") or ""),
                    "kind": str(row.get("kind") or ""),
                    "filename": str(row.get("filename") or ""),
                    "mime_type": str(row.get("mime_type") or ""),
                    "local_path": str(row.get("local_path") or ""),
                    "caption": str(row.get("caption") or ""),
                }
            )
        return out
