import smbclient
from config.settings import settings
import structlog

log = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".pptx", ".txt", ".md"}


class SMBClient:
    def __init__(self):
        if not all([settings.SMB_HOST, settings.SMB_USERNAME, settings.SMB_PASSWORD]):
            raise ValueError("SMB_HOST, SMB_USERNAME, SMB_PASSWORD chưa được cấu hình")

        smbclient.register_session(
            settings.SMB_HOST,
            username=settings.SMB_USERNAME,
            password=settings.SMB_PASSWORD,
        )
        self._host  = settings.SMB_HOST
        self._share = settings.SMB_SHARE

    def _unc(self, path: str = "") -> str:
        """Build UNC path: \\host\share\path"""
        base = f"\\\\{self._host}\\{self._share}"
        return f"{base}\\{path}".rstrip("\\") if path else base

    def list_files(self, path: str = "") -> list[dict]:
        """Đệ quy liệt kê toàn bộ files hỗ trợ."""
        result = []
        try:
            unc = self._unc(path)
            for entry in smbclient.scandir(unc):
                rel_path = f"{path}\\{entry.name}".lstrip("\\")
                if entry.is_dir():
                    result.extend(self.list_files(rel_path))
                else:
                    ext = "." + entry.name.rsplit(".", 1)[-1].lower() if "." in entry.name else ""
                    if ext in SUPPORTED_EXTENSIONS:
                        stat = entry.stat()
                        result.append({
                            "name":     entry.name,
                            "path":     rel_path,
                            "ext":      ext,
                            "size":     stat.st_size,
                            "modified": stat.st_mtime,
                        })
        except Exception as e:
            log.error("smb.list_files.failed", path=path, error=str(e))
        return result

    def read_file(self, path: str) -> bytes:
        """Đọc file từ SMB share trả về bytes."""
        with smbclient.open_file(self._unc(path), mode="rb") as f:
            return f.read()

    def test_connection(self) -> bool:
        try:
            smbclient.listdir(self._unc())
            return True
        except Exception as e:
            log.error("smb.test_connection.failed", error=str(e))
            return False