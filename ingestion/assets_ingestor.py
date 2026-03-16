from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog
from PIL import Image
from sqlalchemy import text

from config.settings import settings
from connectors.confluence.confluence_client import ConfluenceClient
from persistence.asset_repository import AssetRepository
from storage.assets.local_store import LocalAssetStore
from utils.vision import describe_images_batch


log = structlog.get_logger()


_RE_CONFLUENCE_IMAGE = re.compile(r"\[\[IMAGE:([^\]]+)\]\]")
_RE_CONFLUENCE_URL = re.compile(r"\[\[IMAGE_URL:([^\]]+)\]\]")
_RE_SLACK_FILE = re.compile(r"\[\[SLACK_FILE:([^\]]+)\]\]")
_RE_JIRA_ATTACHMENT = re.compile(r"\[\[JIRA_ATTACHMENT:([^\]]+)\]\]")
_RE_IMPORTED_ASSET = re.compile(r"\[\[IMPORTED_ASSET:([^\]]+)\]\]")

_RE_ASSET_ID = re.compile(r"\[\[ASSET_ID:([0-9a-fA-F-]{36})\]\]")


def _guess_mime_from_filename(filename: str) -> str:
    name = (filename or "").lower().strip()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    if name.endswith(".bmp"):
        return "image/bmp"
    if name.endswith(".tif") or name.endswith(".tiff"):
        return "image/tiff"
    return "application/octet-stream"


def _jira_http_auth() -> tuple[str, str] | None:
    user = str(settings.JIRA_USERNAME or "").strip()
    token = str(settings.JIRA_API_TOKEN or "").strip()
    if user and token:
        return (user, token)
    return None


@dataclass(frozen=True)
class Placeholder:
    kind: str
    key: str
    raw: str


class AssetIngestor:
    def __init__(self, session):
        self._session = session
        self._repo = AssetRepository(session)
        self._store = LocalAssetStore()

    @staticmethod
    def extract_asset_ids(text: str) -> list[str]:
        return [m.group(1) for m in _RE_ASSET_ID.finditer(text or "")]

    def _scan_placeholders(self, content: str) -> list[Placeholder]:
        text = str(content or "")
        found: list[Placeholder] = []

        for m in _RE_CONFLUENCE_IMAGE.finditer(text):
            raw = m.group(0)
            key = m.group(1).strip()
            if key:
                found.append(Placeholder(kind="confluence_attachment", key=key, raw=raw))

        for m in _RE_SLACK_FILE.finditer(text):
            raw = m.group(0)
            key = m.group(1).strip()
            if key:
                found.append(Placeholder(kind="slack_file", key=key, raw=raw))

        for m in _RE_JIRA_ATTACHMENT.finditer(text):
            raw = m.group(0)
            key = m.group(1).strip()
            if key:
                found.append(Placeholder(kind="jira_attachment", key=key, raw=raw))

        for m in _RE_IMPORTED_ASSET.finditer(text):
            raw = m.group(0)
            key = m.group(1).strip()
            if key:
                found.append(Placeholder(kind="imported", key=key, raw=raw))

        # IMAGE_URL placeholders are best-effort only (often external/cors-restricted).
        for m in _RE_CONFLUENCE_URL.finditer(text):
            raw = m.group(0)
            key = m.group(1).strip()
            if key and key.startswith("http"):
                found.append(Placeholder(kind="http_url", key=key, raw=raw))

        # Preserve order but dedupe per (kind,key).
        seen: set[tuple[str, str]] = set()
        ordered: list[Placeholder] = []
        for p in found:
            k = (p.kind, p.key)
            if k in seen:
                continue
            seen.add(k)
            ordered.append(p)
        return ordered

    async def enrich_document(self, doc: Any) -> dict[str, Any]:
        """
        Download/capture images referenced in doc.content, store them locally + in DB,
        and inject caption/OCR text into doc.content for embedding + retrieval.

        Returns: {"content": str, "asset_ids": list[str], "ingested": int, "replacements": dict[str,str]}
        """
        content = str(getattr(doc, "content", "") or "")
        if not content.strip():
            return {"content": content, "asset_ids": [], "ingested": 0, "replacements": {}}

        placeholders = self._scan_placeholders(content)
        if not placeholders:
            return {"content": content, "asset_ids": [], "ingested": 0, "replacements": {}}

        max_per_doc = max(0, int(settings.VISION_MAX_IMAGES_PER_DOC or 0))
        if max_per_doc == 0:
            return {"content": content, "asset_ids": [], "ingested": 0, "replacements": {}}
        placeholders = placeholders[:max_per_doc]

        doc_id = str(getattr(doc, "id", "") or "").strip()
        if not doc_id:
            return {"content": content, "asset_ids": [], "ingested": 0, "replacements": {}}

        meta = getattr(doc, "metadata", {}) or {}
        if not isinstance(meta, dict):
            meta = {}

        # Multi-instance connectors: load credentials from DB when connector_key is set (e.g. "jira:<uuid>").
        connector_key = str(meta.get("connector_key") or "").strip()
        connector_type = connector_key.split(":", 1)[0] if ":" in connector_key else connector_key
        instance_id = connector_key.split(":", 1)[1] if ":" in connector_key else ""

        async def _fetch_instance() -> dict[str, Any]:
            if not (connector_type and instance_id):
                return {}
            try:
                r = await self._session.execute(
                    text(
                        """
                        SELECT connector_type, base_url, auth_type, username, secret, extra
                        FROM connector_instances
                        WHERE connector_type = :t AND id::text = :id
                        """
                    ),
                    {"t": connector_type, "id": instance_id},
                )
                row = r.mappings().first()
                return dict(row) if row else {}
            except Exception:
                return {}

        instance = await _fetch_instance()
        inst_base_url = str(instance.get("base_url") or "").strip() or None
        inst_auth_type = str(instance.get("auth_type") or "").strip().lower() or None
        inst_username = str(instance.get("username") or "").strip() or None
        inst_secret = str(instance.get("secret") or "").strip() or None

        # Preload source-specific lookup tables.
        confluence_page_id = str(meta.get("page_id") or "").strip()
        confluence_attachments: dict[str, dict] = {}
        if confluence_page_id:
            try:
                conf_client = ConfluenceClient(
                    base_url=inst_base_url if connector_type == "confluence" else None,
                    api_token=inst_secret if connector_type == "confluence" else None,
                    username=inst_username if connector_type == "confluence" else None,
                    auth_type=inst_auth_type if connector_type == "confluence" else None,
                )
                items = await asyncio.to_thread(conf_client.list_attachments, confluence_page_id, 200)
                for it in items:
                    fn = str(it.get("filename") or "").strip()
                    if fn:
                        confluence_attachments[fn.lower()] = it
            except Exception:
                confluence_attachments = {}

        slack_files: dict[str, dict] = {}
        for f in (meta.get("slack_files") or []):
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id") or "").strip()
            if fid:
                slack_files[fid] = f

        jira_attachments: dict[str, dict] = {}
        for a in (meta.get("image_attachments") or []):
            if not isinstance(a, dict):
                continue
            aid = str(a.get("id") or "").strip()
            if aid:
                jira_attachments[aid] = a

        imported: dict[str, dict] = {}
        for a in (meta.get("import_assets") or []):
            if not isinstance(a, dict):
                continue
            iid = str(a.get("import_id") or "").strip()
            if iid:
                imported[iid] = a

        # Fetch image bytes for each placeholder.
        fetched: list[dict] = []
        for p in placeholders:
            item = {"placeholder": p, "bytes": b"", "filename": "", "mime_type": "", "source_ref": "", "staged_path": ""}

            if p.kind == "confluence_attachment":
                it = confluence_attachments.get(p.key.lower())
                if it:
                    item["filename"] = str(it.get("filename") or p.key)
                    item["mime_type"] = str(it.get("mime_type") or "") or _guess_mime_from_filename(item["filename"])
                    item["source_ref"] = confluence_page_id
                    download_url = str(it.get("download_url") or "").strip()
                    if download_url:
                        conf_client = ConfluenceClient(
                            base_url=inst_base_url if connector_type == "confluence" else None,
                            api_token=inst_secret if connector_type == "confluence" else None,
                            username=inst_username if connector_type == "confluence" else None,
                            auth_type=inst_auth_type if connector_type == "confluence" else None,
                        )
                        item["bytes"] = await asyncio.to_thread(conf_client.download_attachment, download_url)

            elif p.kind == "slack_file":
                f = slack_files.get(p.key) or {}
                item["filename"] = str(f.get("name") or "slack_image").strip() or "slack_image"
                item["mime_type"] = str(f.get("mimetype") or "").strip() or _guess_mime_from_filename(item["filename"])
                item["source_ref"] = p.key
                url = str(f.get("url_private_download") or f.get("url_private") or "").strip()
                slack_token = inst_secret if connector_type == "slack" and inst_secret else settings.SLACK_BOT_TOKEN
                if url and slack_token:
                    try:
                        async with httpx.AsyncClient(timeout=60) as client:
                            resp = await client.get(url, headers={"Authorization": f"Bearer {slack_token}"})
                            resp.raise_for_status()
                            item["bytes"] = resp.content or b""
                    except Exception as exc:
                        log.warning("assets.slack.download_failed", file_id=p.key, error=str(exc))

            elif p.kind == "jira_attachment":
                a = jira_attachments.get(p.key) or {}
                item["filename"] = str(a.get("filename") or "jira_attachment").strip() or "jira_attachment"
                item["mime_type"] = str(a.get("mime_type") or "").strip() or _guess_mime_from_filename(item["filename"])
                item["source_ref"] = p.key
                url = str(a.get("content_url") or "").strip()
                if url:
                    try:
                        # Prefer instance credentials when available.
                        auth = (inst_username, inst_secret) if (connector_type == "jira" and inst_auth_type == "basic" and inst_username and inst_secret) else _jira_http_auth()
                        bearer = inst_secret if (connector_type == "jira" and inst_auth_type != "basic" and inst_secret) else settings.JIRA_API_TOKEN
                        headers = {"Accept": "*/*"}
                        async with httpx.AsyncClient(timeout=60, verify=bool(getattr(settings, "JIRA_VERIFY_TLS", True))) as client:
                            if auth:
                                resp = await client.get(url, auth=auth, headers=headers)
                            else:
                                resp = await client.get(url, headers={**headers, "Authorization": f"Bearer {bearer}"})
                            resp.raise_for_status()
                            item["bytes"] = resp.content or b""
                    except Exception as exc:
                        log.warning("assets.jira.download_failed", attachment_id=p.key, error=str(exc))

            elif p.kind == "imported":
                a = imported.get(p.key) or {}
                staged_path = str(a.get("staged_path") or "").strip()
                item["filename"] = str(a.get("filename") or "imported_image").strip() or "imported_image"
                item["mime_type"] = str(a.get("mime_type") or "").strip() or _guess_mime_from_filename(item["filename"])
                item["source_ref"] = p.key
                if staged_path:
                    try:
                        item["bytes"] = Path(staged_path).read_bytes()
                        item["staged_path"] = staged_path
                    except Exception as exc:
                        log.warning("assets.import.read_failed", path=staged_path, error=str(exc))

            elif p.kind == "http_url":
                item["filename"] = "image"
                item["mime_type"] = "application/octet-stream"
                item["source_ref"] = p.key
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(p.key)
                        resp.raise_for_status()
                        item["bytes"] = resp.content or b""
                except Exception:
                    pass

            if item["bytes"]:
                fetched.append(item)

        if not fetched:
            return {"content": content, "asset_ids": [], "ingested": 0, "replacements": {}}

        # Batch caption/OCR (optional).
        captions = await describe_images_batch(
            [{"image_bytes": it["bytes"], "hint": str(getattr(doc, "title", "") or "")[:120]} for it in fetched],
            concurrency=2,
        )

        # Persist + inject into content.
        created_ids: list[str] = []
        replacements: dict[str, str] = {}
        for idx, it in enumerate(fetched):
            p: Placeholder = it["placeholder"]
            data = it["bytes"]
            filename = str(it["filename"] or "").strip() or "image"
            mime_type = str(it["mime_type"] or "").strip() or _guess_mime_from_filename(filename)
            caption = str(captions[idx] if idx < len(captions) else "" or "").strip()

            # Dedup by (doc_id, sha256).
            sha = None
            try:
                import hashlib
                sha = hashlib.sha256(data).hexdigest()
            except Exception:
                sha = None

            existing = None
            if sha:
                try:
                    existing = await self._repo.find_by_doc_sha256(document_id=doc_id, sha256=sha)
                except Exception:
                    existing = None

            if existing:
                asset_id = str(existing.get("id") or "")
                created_ids.append(asset_id)
                # Still replace placeholder to ensure chunk->asset linking.
                replacement = f"[Image: {filename}] {caption}".strip()
                replacement = f"{replacement} [[ASSET_ID:{asset_id}]]".strip()
                content = content.replace(p.raw, replacement)
                replacements[p.raw] = replacement

                # Cleanup: imported staging files are temporary.
                staged_path = str(it.get("staged_path") or "").strip()
                if staged_path:
                    try:
                        Path(staged_path).unlink(missing_ok=True)  # py3.8+ on Windows supports missing_ok
                    except TypeError:
                        try:
                            pth = Path(staged_path)
                            if pth.exists():
                                pth.unlink()
                        except Exception:
                            pass
                    except Exception:
                        pass
                continue

            # Compute basic dimensions (best-effort).
            width = None
            height = None
            try:
                from io import BytesIO

                with Image.open(BytesIO(data)) as im:
                    width, height = im.size
            except Exception:
                width = None
                height = None

            asset_uuid = None
            try:
                import uuid

                asset_uuid = str(uuid.uuid4())
            except Exception:
                asset_uuid = None

            if not asset_uuid:
                continue

            try:
                stored = self._store.save(
                    asset_id=asset_uuid,
                    document_id=doc_id,
                    filename=filename,
                    mime_type=mime_type,
                    data=data,
                )
            except Exception as exc:
                log.warning("assets.store_failed", doc_id=doc_id, filename=filename, error=str(exc))
                continue

            db_asset_id = await self._repo.upsert_asset(
                document_id=doc_id,
                source=(getattr(getattr(doc, "source", ""), "value", None) or str(getattr(doc, "source", "") or "")).strip(),
                source_ref=str(it.get("source_ref") or "").strip() or None,
                kind="image",
                filename=filename,
                mime_type=mime_type,
                bytes_size=stored.bytes,
                sha256=stored.sha256,
                local_path=stored.local_path,
                caption=caption or None,
                ocr_text=None,
                width=width,
                height=height,
                meta={"placeholder_kind": p.kind, "placeholder_key": p.key},
            )

            created_ids.append(db_asset_id)
            replacement = f"[Image: {filename}] {caption}".strip()
            replacement = f"{replacement} [[ASSET_ID:{db_asset_id}]]".strip()
            content = content.replace(p.raw, replacement)
            replacements[p.raw] = replacement

            # Cleanup: imported staging files are temporary.
            staged_path = str(it.get("staged_path") or "").strip()
            if staged_path:
                try:
                    Path(staged_path).unlink(missing_ok=True)
                except TypeError:
                    try:
                        pth = Path(staged_path)
                        if pth.exists():
                            pth.unlink()
                    except Exception:
                        pass
                except Exception:
                    pass

        return {"content": content, "asset_ids": created_ids, "ingested": len(created_ids), "replacements": replacements}
