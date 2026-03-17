from typing import List, Any, Dict
from .base import BaseChunker

class TextChunker(BaseChunker):
    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản thô (raw text) hoặc tài liệu chung thành các chunk.
        """
        # TODO: Implement Text chunking logic
        return [{"text": text, "metadata": {"source": "text"}}]