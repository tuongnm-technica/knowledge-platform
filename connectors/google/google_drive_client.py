import io
import json
import structlog
from typing import Optional, List, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

log = structlog.get_logger()

class GoogleDriveClient:
    """
    Client tương tác với Google Drive API sử dụng Service Account.
    Hỗ trợ tìm kiếm các bản ghi cuộc họp và tải bản chép lời (Transcripts).
    """
    def __init__(self, service_account_info: Dict[str, Any]):
        self._creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        self._service = build('drive', 'v3', credentials=self._creds)

    def list_files(self, query: str = "", page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Liệt kê các file trong Drive dựa trên query.
        Ví dụ: "name contains 'Meeting Recordings'" hoặc "mimeType = 'text/plain'"
        """
        try:
            results = self._service.files().list(
                q=query,
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime, owners, parents)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            log.error("google.drive.list_files.failed", error=str(e))
            return []

    def get_file_content(self, file_id: str) -> Optional[str]:
        """
        Tải nội dung của một file văn bản (txt, vtt).
        """
        try:
            request = self._service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            return fh.getvalue().decode('utf-8')
        except Exception as e:
            log.error("google.drive.get_content.failed", file_id=file_id, error=str(e))
            return None

    def find_meeting_transcripts(self, folder_name: str = "Meeting Recordings") -> List[Dict[str, Any]]:
        """
        Tiện ích tìm kiếm các file transcript trong thư mục cuộc họp.
        """
        # 1. Tìm ID của thư mục "Meeting Recordings"
        folders = self.list_files(query=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'")
        if not folders:
            log.warning("google.drive.folder_not_found", folder=folder_name)
            # Nếu không tìm thấy thư mục cụ thể, tìm kiếm toàn cục các file .vtt/.txt có tên "Meeting"
            return self.list_files(query="name contains 'Meeting' and (mimeType = 'text/plain' or name contains '.vtt')")

        folder_id = folders[0]['id']
        # 2. Liệt kê các file văn bản trong thư mục đó
        return self.list_files(query=f"'{folder_id}' in parents and (mimeType = 'text/plain' or name contains '.vtt')")
