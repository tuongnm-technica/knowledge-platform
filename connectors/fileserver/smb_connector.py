import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.fileserver.smb_client import SMBClient
from connectors.fileserver.file_parser import FileParser
from config.settings import settings
import structlog

log = structlog.get_logger()

# ─── Giới hạn dung lượng file tối đa (bytes) ─────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class SMBConnector(BaseConnector):

    def __init__(self):
        self.validate_config()
        self._client = SMBClient()
        self._parser = FileParser()

    def validate_config(self) -> bool:
        if not all([settings.SMB_HOST, settings.SMB_USERNAME, settings.SMB_PASSWORD, settings.SMB_SHARE]):
            raise ValueError("SMB_HOST, SMB_USERNAME, SMB_PASSWORD, SMB_SHARE chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        files     = self._client.list_files(settings.SMB_BASE_PATH)
        log.info("smb.fetch.start", total_files=len(files))

        for file_info in files:
            try:
                # Bỏ qua file quá lớn
                if file_info["size"] > MAX_FILE_SIZE:
                    log.warning("smb.skip.too_large", path=file_info["path"], size=file_info["size"])
                    continue

                data    = self._client.read_file(file_info["path"])
                content = self._parser.parse(file_info["name"], data)

                if not content or len(content.strip()) < 30:
                    log.debug("smb.skip.empty", path=file_info["path"])
                    continue

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.FILE_SERVER,
                    source_id=file_info["path"],
                    title=file_info["name"],
                    content=content,
                    url=f"\\\\{settings.SMB_HOST}\\{settings.SMB_SHARE}\\{file_info['path']}",
                    author="file_server",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.fromtimestamp(file_info["modified"]),
                    metadata={
                        "path":      file_info["path"],
                        "extension": file_info["ext"],
                        "size":      file_info["size"],
                        "share":     settings.SMB_SHARE,
                    },
                    permissions=["group_all_employees"],
                )
                documents.append(doc)
                log.info("smb.file.ok", name=file_info["name"], ext=file_info["ext"])

            except Exception as e:
                log.error("smb.file.error", path=file_info.get("path"), error=str(e))
                continue

        log.info("smb.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        return ["group_all_employees"]