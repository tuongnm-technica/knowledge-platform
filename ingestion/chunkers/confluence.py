from typing import List, Any, Dict
from .base import BaseChunker

class ConfluenceChunker(BaseChunker):
    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản từ Confluence thành các chunk.
        """
        # TODO: Cập nhật logic chia tách (chunking) thực tế cho Confluence ở đây.
        # Trả về dữ liệu mẫu để tránh lỗi
        return [{"text": text, "metadata": {"source": "confluence"}}]