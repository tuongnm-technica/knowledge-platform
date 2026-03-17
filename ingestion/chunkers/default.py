from __future__ import annotations

from models.document import Chunk
from .base import BaseChunker


class WordCountChunker(BaseChunker):
    """Default chunker using word count with overlap."""
    def chunk(self, document_id: str, **kwargs) -> list[Chunk]:
        content = kwargs.get("content", "")
        return self._word_count_chunk(document_id, content)