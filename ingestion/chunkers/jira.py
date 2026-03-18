from typing import List
from models.document import Chunk
from .base import BaseChunker

class JiraChunker(BaseChunker):
    def chunk(self, document_id: str, **kwargs) -> List[Chunk]:
        """
        Chia nhỏ văn bản từ Jira Tickets thành các chunk.
        """
        text = kwargs.get("content", "")
        return self._word_count_chunk(document_id, text)