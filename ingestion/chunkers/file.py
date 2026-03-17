from typing import List, Any, Dict
from .base import BaseChunker

class FileChunker(BaseChunker):
    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản từ các file (PDF, DOCX, v.v.) thành các chunk.
        """
        # TODO: Implement File chunking logic
        return [{"text": text, "metadata": {"source": "file"}}]