import smbclient
from config.settings import settings
import structlog

log = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".pptx", ".txt", ".md"}


class SMBClient:
    def __init__(
        self,
        *,
        host: str | None = None,
        share: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        host = (host or settings.SMB_HOST or "").strip()
        share = (share or settings.SMB_SHARE or "").strip()
        username = (username or settings.SMB_USERNAME or "").strip()
        password = (password or settings.SMB_PASSWORD or "").strip()

        if not host or not username or not password:
            raise ValueError("SMB_HOST, SMB_USERNAME, SMB_PASSWORD chưa được cấu hình")

        smbclient.register_session(host, username=username, password=password)
        self._host = host
        self._share = share or settings.SMB_SHARE

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

    def list_top_folders(self, path: str = "") -> list[str]:
        """
        List first-level folders under SMB share (used by UI discovery).
        """
        folders: list[str] = []
        try:
            unc = self._unc(path)
            for entry in smbclient.scandir(unc):
                try:
                    if entry.is_dir():
                        folders.append(entry.name)
                except Exception:
                    continue
        except Exception as e:
            log.error("smb.list_top_folders.failed", path=path, error=str(e))
        # stable order
        return sorted({f for f in folders if f})

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
