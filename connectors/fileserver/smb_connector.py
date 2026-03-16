import uuid
from datetime import datetime
from pathlib import Path
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.fileserver.smb_client import SMBClient
from connectors.fileserver.file_parser import FileParser
from permissions.workspace_config import get_smb_workspace  # ← thêm
from config.settings import settings
import structlog

log = structlog.get_logger()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class SMBConnector(BaseConnector):

    def __init__(
        self,
        *,
        folders: set[str] | None = None,
        host: str | None = None,
        share: str | None = None,
        username: str | None = None,
        password: str | None = None,
        base_path: str | None = None,
    ):
        self._host = (host or settings.SMB_HOST or "").strip()
        self._share = (share or settings.SMB_SHARE or "").strip()
        self._username = (username or settings.SMB_USERNAME or "").strip()
        self._password = (password or settings.SMB_PASSWORD or "").strip()
        self._base_path = (base_path or settings.SMB_BASE_PATH or "").strip() or "\\"

        self.validate_config()
        self._client = SMBClient(host=self._host, share=self._share, username=self._username, password=self._password)
        self._parser = FileParser()
        self._folders = {f.strip() for f in (folders or set()) if f and str(f).strip()}

    def validate_config(self) -> bool:
        if not self._host or not self._username or not self._password or not self._share:
            raise ValueError("SMB_HOST, SMB_USERNAME, SMB_PASSWORD, SMB_SHARE chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        files     = self._client.list_files(self._base_path)
        log.info("smb.fetch.start", total_files=len(files))

        for file_info in files:
            try:
                if file_info["size"] > MAX_FILE_SIZE:
                    log.warning("smb.skip.too_large", path=file_info["path"], size=file_info["size"])
                    continue

                data    = self._client.read_file(file_info["path"])

                ext = str(file_info.get("ext") or "").strip().lower()
                if ext and not ext.startswith("."):
                    ext = "." + ext

                # If the file is an image, stage it so the ingestion pipeline can caption/OCR it.
                # This avoids losing screenshots/diagrams which are common in office file shares.
                if ext in _IMAGE_EXTS and data:
                    import_id = str(uuid.uuid4())
                    assets_root = Path(settings.ASSETS_DIR or "assets")
                    import_dir = assets_root / "_imports"
                    import_dir.mkdir(parents=True, exist_ok=True)
                    safe_name = Path(file_info["name"]).name.replace(" ", "_")
                    staged = import_dir / f"{import_id}-{safe_name}"
                    with open(staged, "wb") as f:
                        f.write(data)

                    # Top-level folder làm permission key
                    path_parts = file_info["path"].replace("/", "\\").split("\\")
                    top_folder = path_parts[0] if path_parts else "General"
                    if self._folders and top_folder not in self._folders:
                        continue

                    permissions  = [f"group_file_folder_{str(top_folder or '').strip().lower()}"]
                    workspace_id = get_smb_workspace(top_folder)  # ← thêm

                    doc = Document(
                        id=str(uuid.uuid4()),
                        source=SourceType.FILE_SERVER,
                        source_id=file_info["path"],
                        title=file_info["name"],
                        content=f"[Image file] {file_info['name']}\n[[IMPORTED_ASSET:{import_id}]]",
                        url=f"\\\\{self._host}\\{self._share}\\{file_info['path']}",
                        author="file_server",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.fromtimestamp(file_info["modified"]),
                        metadata={
                            "path":          file_info["path"],
                            "extension":     ext,
                            "size":          file_info["size"],
                            "share":         self._share,
                            "top_folder":    top_folder,
                            "permission_id": f"group_file_folder_{str(top_folder or '').strip().lower()}",
                            "import_assets": [
                                {
                                    "import_id": import_id,
                                    "filename": file_info["name"],
                                    "mime_type": f"image/{ext.lstrip('.')}",
                                    "staged_path": str(staged).replace("\\", "/"),
                                }
                            ],
                        },
                        permissions=permissions,
                        workspace_id=workspace_id,  # ← thêm
                    )
                    documents.append(doc)
                    log.info("smb.image.ok", name=file_info["name"], folder=top_folder)
                    continue

                content = self._parser.parse(file_info["name"], data)

                if not content or len(content.strip()) < 30:
                    log.debug("smb.skip.empty", path=file_info["path"])
                    continue

                # Top-level folder làm permission key
                path_parts = file_info["path"].replace("/", "\\").split("\\")
                top_folder = path_parts[0] if path_parts else "General"
                if self._folders and top_folder not in self._folders:
                    continue

                permissions  = [f"group_file_folder_{str(top_folder or '').strip().lower()}"]
                workspace_id = get_smb_workspace(top_folder)  # ← thêm

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.FILE_SERVER,
                    source_id=file_info["path"],
                    title=file_info["name"],
                    content=content,
                    url=f"\\\\{self._host}\\{self._share}\\{file_info['path']}",
                    author="file_server",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.fromtimestamp(file_info["modified"]),
                    metadata={
                        "path":          file_info["path"],
                        "extension":     file_info["ext"],
                        "size":          file_info["size"],
                        "share":         self._share,
                        "top_folder":    top_folder,
                        "permission_id": f"group_file_folder_{str(top_folder or '').strip().lower()}",
                    },
                    permissions=permissions,
                    workspace_id=workspace_id,  # ← thêm
                )
                documents.append(doc)
                log.info("smb.file.ok", name=file_info["name"], folder=top_folder)

            except Exception as e:
                log.error("smb.file.error", path=file_info.get("path"), error=str(e))
                continue

        log.info("smb.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        parts      = source_id.replace("/", "\\").split("\\")
        top_folder = parts[0] if parts else "General"
        return [f"group_file_folder_{str(top_folder or '').strip().lower()}"]
