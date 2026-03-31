import uuid
from datetime import datetime, timedelta
import structlog
from typing import List, Optional, Set

from connectors.base.base_connector import BaseConnector
from connectors.zoom.zoom_client import ZoomClient
from models.document import Document, SourceType

log = structlog.get_logger()

class ZoomConnector(BaseConnector):
    """
    Connector để nạp dữ liệu từ Zoom Cloud Recordings (Transcripts).
    """
    
    def __init__(
        self, 
        *, 
        account_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token: Optional[str] = None,
        recording_ids: Optional[Set[str]] = None
    ):
        self._client = ZoomClient(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            token=token
        )
        self._recording_ids = recording_ids or set()

    def validate_config(self) -> bool:
        """Kiểm tra cấu hình có hợp lệ không."""
        return True # Client will fail on first request if invalid

    async def get_permissions(self, source_id: str) -> List[str]:
        """Quyền truy cập mặc định cho tài liệu Zoom."""
        return ["group_zoom_all"]

    async def fetch_documents(self) -> List[Document]:
        """
        Lấy danh sách các cuộc họp và tải bản chép lời (transcript).
        """
        documents = []
        
        # 1. Lấy danh sách meetings có recordings (mặc định lấy 30 ngày gần nhất)
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        meetings = await self._client.list_recordings(from_date=from_date)
        
        log.info("zoom.fetch.start", meeting_count=len(meetings))
        
        for meeting in meetings:
            meeting_id = meeting.get("id")
            uuid_str = meeting.get("uuid")
            topic = meeting.get("topic", "Untitled Meeting")
            start_time_str = meeting.get("start_time")
            
            # Lọc nếu có danh sách ID cụ thể
            if self._recording_ids and str(meeting_id) not in self._recording_ids:
                log.debug("zoom.skip.filtered", meeting_id=meeting_id, topic=topic)
                continue
                
            try:
                # 2. Lấy nội dung transcript
                transcript_text = await self._client.get_recording_transcripts(meeting_id)
                
                if not transcript_text or len(transcript_text.strip()) < 50:
                    log.debug("zoom.skip.empty_transcript", meeting_id=meeting_id)
                    continue

                # 3. Tạo Document object
                doc_id = str(uuid.uuid4())
                created_at = datetime.utcnow()
                if start_time_str:
                    try:
                        # Zoom format: 2021-03-25T06:33:04Z
                        created_at = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        pass

                documents.append(
                    Document(
                        id=doc_id,
                        source=SourceType.ZOOM,
                        source_id=str(meeting_id),
                        title=f"[Zoom] {topic}",
                        content=transcript_text,
                        url=f"https://zoom.us/rec/play/{meeting_id}", # Placeholder link
                        author=meeting.get("host_id", "zoom"),
                        created_at=created_at,
                        updated_at=datetime.utcnow(),
                        metadata={
                            "meeting_id": meeting_id,
                            "uuid": uuid_str,
                            "topic": topic,
                            "start_time": start_time_str,
                            "duration": meeting.get("duration"),
                            "total_size": meeting.get("total_size"),
                            "recording_count": meeting.get("recording_count"),
                        },
                        permissions=["group_zoom_all"]
                    )
                )
                log.info("zoom.meeting.done", topic=topic, meeting_id=meeting_id)

            except Exception as e:
                log.error("zoom.meeting.failed", meeting_id=meeting_id, error=str(e))
                continue
                
        log.info("zoom.fetch.done", total_documents=len(documents))
        return documents
