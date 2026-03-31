import httpx
import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

log = structlog.get_logger()

class ZoomClient:
    """
    Client cho Zoom API v2.
    Hỗ trợ Server-to-Server OAuth hoặc Static Bearer Token.
    """
    
    BASE_URL = "https://api.zoom.us/v2"
    AUTH_URL = "https://zoom.us/oauth/token"

    def __init__(
        self, 
        *, 
        account_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token: Optional[str] = None
    ):
        self._account_id = account_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._static_token = token
        self._access_token: Optional[str] = None
        self._token_expires_at: datetime = datetime.min

    async def _get_access_token(self) -> str:
        """Lấy access token via Server-to-Server OAuth hoặc dùng static token."""
        if self._static_token:
            return self._static_token
            
        if self._access_token and datetime.utcnow() < self._token_expires_at:
            return self._access_token

        if not all([self._account_id, self._client_id, self._client_secret]):
            raise ValueError("Thiếu credentials cho Zoom Server-to-Server OAuth")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.AUTH_URL,
                    params={
                        "grant_type": "account_credentials",
                        "account_id": self._account_id
                    },
                    auth=(self._client_id, self._client_secret)
                )
                response.raise_for_status()
                data = response.json()
                self._access_token = data["access_token"]
                # Expires in usually 3600s
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                return self._access_token
            except Exception as e:
                log.error("zoom.auth.failed", error=str(e))
                raise ConnectionError(f"Không thể lấy Zoom access token: {str(e)}")

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        token = await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 401:
                 # Token force refresh next time if it was an expired token error
                 self._access_token = None
            response.raise_for_status()
            return response.json() if response.content else None

    async def test_connection(self) -> bool:
        """Kiểm tra kết nối bằng cách lấy thông tin user hiện tại."""
        try:
            await self._request("GET", "/users/me")
            return True
        except Exception as e:
            log.error("zoom.test_connection.failed", error=str(e))
            return False

    async def list_recordings(self, user_id: str = "me", from_date: Optional[str] = None) -> List[Dict]:
        """Liệt kê danh sách Cloud Recordings của user."""
        params = {"page_size": 100}
        if from_date:
            params["from"] = from_date # Format YYYY-MM-DD
            
        try:
            data = await self._request("GET", f"/users/{user_id}/recordings", params=params)
            return data.get("meetings", [])
        except Exception as e:
            log.error("zoom.list_recordings.failed", error=str(e))
            return []

    async def get_recording_transcripts(self, meeting_id: Any) -> str:
        """Lấy nội dung bản chép lời từ một meeting recording."""
        try:
            # 1. Lấy thông tin chi tiết recording
            data = await self._request("GET", f"/meetings/{meeting_id}/recordings")
            recording_files = data.get("recording_files", [])
            
            # 2. Tìm file transcript (TRANSCRIPT hoặc TIMELINE)
            transcript_file = next(
                (f for f in recording_files if f.get("file_type") == "TRANSCRIPT"), 
                None
            )
            
            if not transcript_file:
                log.warning("zoom.transcript.not_found", meeting_id=meeting_id)
                return ""
            
            download_url = transcript_file.get("download_url")
            if not download_url:
                return ""

            # 3. Download transcript (cần token trong query hoặc header tùy API version)
            token = await self._get_access_token()
            async with httpx.AsyncClient() as client:
                # Zoom download_url often requires the token as a query param or redirect handles it
                res = await client.get(f"{download_url}?access_token={token}")
                res.raise_for_status()
                return res.text
                
        except Exception as e:
            log.error("zoom.get_transcript.failed", meeting_id=meeting_id, error=str(e))
            return ""
