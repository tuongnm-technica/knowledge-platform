import json
import structlog
from datetime import datetime
from typing import List, Dict, Any, Optional

from connectors.base.base_connector import BaseConnector
from connectors.google.google_drive_client import GoogleDriveClient
from models.document import Document, SourceType

log = structlog.get_logger()

class GoogleMeetConnector(BaseConnector):
    """
    Connector để nạp bản ghi cuộc họp và transcript từ Google Meet (thông qua Drive).
    """
    def __init__(
        self,
        service_account_json: str,
        folder_name: str = "Meeting Recordings"
    ):
        try:
            self._creds_info = json.loads(service_account_json)
        except Exception as e:
            log.error("google.meet.invalid_creds", error=str(e))
            self._creds_info = {}
            
        self._folder_name = folder_name or "Meeting Recordings"
        self._client = None
        if self._creds_info:
            self._client = GoogleDriveClient(self._creds_info)

    async def fetch_documents(self, last_sync: Optional[datetime] = None) -> List[Document]:
        """
        Quét Drive để tìm các bản chép lời cuộc họp mới.
        """
        if not self._client:
            return []

        log.info("google.meet.fetch.start", folder=self._folder_name)
        transcripts = self._client.find_meeting_transcripts(self._folder_name)
        documents = []

        for file in transcripts:
            file_id = file['id']
            file_name = file['name']
            created_time_str = file.get('createdTime', '')
            created_time = datetime.fromisoformat(created_time_str.replace('Z', '+00:00')) if created_time_str else datetime.utcnow()

            # Bỏ qua nếu đã đồng bộ (Check last_sync)
            if last_sync and created_time <= last_sync:
                continue

            content = self._client.get_file_content(file_id)
            if not content:
                continue

            doc = Document(
                id=f"google_meet_{file_id}",
                source=SourceType.GOOGLE_MEET,
                source_id=file_id,
                title=file_name.replace(".vtt", "").replace(".txt", ""),
                content=content,
                url=file.get('webViewLink', ''),
                author=file.get('owners', [{}])[0].get('displayName', 'Unknown'),
                created_at=created_time,
                updated_at=created_time, # Drive v3 updatedTime requires extra fetch, using created for now
                metadata={
                    "file_id": file_id,
                    "mime_type": file.get('mimeType'),
                    "folder": self._folder_name
                },
                permissions=['group_google_meet_access'] # Default permission for meetings
            )
            documents.append(doc)

        log.info("google.meet.fetch.done", count=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> List[str]:
        """
        Google Drive permissions phức tạp, tạm thời trả về nhóm truy cập chung.
        """
        return ['group_google_meet_access']

    def validate_config(self) -> bool:
        """Kiểm tra cấu hình Service Account hợp lệ."""
        return bool(self._creds_info and "project_id" in self._creds_info)
