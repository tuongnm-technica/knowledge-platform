from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings


def _safe_filename(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "asset"
    name = re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE)
    name = name.strip("._")
    return name[:120] if name else "asset"


def _ext_from_mime(mime_type: str | None) -> str:
    mt = (mime_type or "").lower().strip()
    if mt in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if mt == "image/png":
        return ".png"
    if mt == "image/webp":
        return ".webp"
    if mt == "image/gif":
        return ".gif"
    if mt == "image/bmp":
        return ".bmp"
    if mt == "image/tiff":
        return ".tiff"
    return ""


@dataclass(frozen=True)
class StoredAsset:
    local_path: str
    sha256: str
    bytes: int


class LocalAssetStore:
    """
    Save binary assets to a local folder (on-prem friendly).

    We store a stable relative path in DB so deployments can relocate the root
    folder without rewriting rows.
    """

    def __init__(self, root_dir: str | None = None):
        root = (root_dir or settings.ASSETS_DIR or "assets").strip()
        self._root = Path(root)

    @property
    def root_dir(self) -> Path:
        return self._root

    def save(
        self,
        *,
        asset_id: str,
        document_id: str,
        filename: str,
        mime_type: str | None,
        data: bytes,
    ) -> StoredAsset:
        if data is None:
            raise ValueError("Missing data")

        size = len(data)
        if size <= 0:
            raise ValueError("Empty asset")
        if size > int(settings.ASSETS_MAX_BYTES or 0):
            raise ValueError(f"Asset too large ({size} bytes)")

        sha256 = hashlib.sha256(data).hexdigest()
        ext = _ext_from_mime(mime_type) or Path(filename or "").suffix.lower()
        safe_name = _safe_filename(Path(filename or "asset").stem)

        # Layout: {ASSETS_DIR}/{doc_id}/{asset_id}-{name}{ext}
        rel_dir = Path(str(document_id))
        rel_name = f"{asset_id}-{safe_name}{ext}"
        rel_path = rel_dir / rel_name
        abs_path = self._root / rel_path

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        # Best-effort atomic write.
        tmp_path = abs_path.with_suffix(abs_path.suffix + ".tmp")
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, abs_path)

        return StoredAsset(local_path=str(rel_path).replace("\\", "/"), sha256=sha256, bytes=size)

