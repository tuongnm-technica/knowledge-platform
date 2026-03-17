from __future__ import annotations

import re
import uuid

from models.document import Chunk
from .base import BaseChunker


class FileChunker(BaseChunker):
    """Paragraph-aware chunking for file server documents."""

    def chunk(self, document_id: str, **kwargs) -> list[Chunk]:
        content = kwargs.get("content", "")
        paragraphs = re.split(r"\n{2,}", content)
        chunks: list[Chunk] = []
        buffer = ""
        index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = f"{buffer}\n\n{para}" if buffer else para
            if len(candidate.split()) > self.chunk_size and buffer:
                chunks.append(Chunk(id=str(uuid.uuid4()), document_id=document_id, content=buffer.strip(), chunk_index=index))
                index += 1
                # Overlap with the last paragraph
                buffer = para
            else:
                buffer = candidate

        if buffer.strip():
            chunks.append(Chunk(id=str(uuid.uuid4()), document_id=document_id, content=buffer.strip(), chunk_index=index))

        return chunks if chunks else self._word_count_chunk(document_id, content)