from __future__ import annotations

import re
import uuid

from models.document import Chunk
from .base import BaseChunker


class JiraChunker(BaseChunker):
    """Jira chunking, aware of headings and paragraphs."""

    def chunk(self, document_id: str, **kwargs) -> list[Chunk]:
        content = (kwargs.get("content", "") or "").strip()
        if not content:
            return []

        if len(content.split()) <= self.chunk_size:
            return [Chunk(id=str(uuid.uuid4()), document_id=document_id, content=content, chunk_index=0)]

        if "\n## " in content or content.lstrip().startswith("## "):
            return self._chunk_by_headings(document_id, content)

        return self._chunk_by_paragraphs(document_id, content)

    def _chunk_by_headings(self, document_id: str, content: str) -> list[Chunk]:
        lines = content.splitlines()
        pre_lines: list[str] = []
        i = 0
        while i < len(lines) and not lines[i].startswith("## "):
            pre_lines.append(lines[i])
            i += 1
        preamble = "\n".join(pre_lines).strip()

        sections: list[tuple[str, str]] = []
        current_title = ""
        current_body: list[str] = []
        for line in lines[i:]:
            if line.startswith("## "):
                if current_body:
                    sections.append((current_title, "\n".join(current_body).strip()))
                current_title = line.strip()
                current_body = []
            else:
                current_body.append(line)
        if current_body:
            sections.append((current_title, "\n".join(current_body).strip()))

        chunks: list[Chunk] = []
        chunk_index = 0
        for title, body in sections:
            if not body.strip():
                continue
            section_text = "\n\n".join(p for p in [preamble, title, body] if p)
            sub = self._word_count_chunk(document_id, section_text, start_index=chunk_index)
            chunks.extend(sub)
            chunk_index += len(sub)
        return chunks if chunks else self._word_count_chunk(document_id, content)

    def _chunk_by_paragraphs(self, document_id: str, content: str) -> list[Chunk]:
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
                buffer = para
            else:
                buffer = candidate
        if buffer.strip():
            chunks.append(Chunk(id=str(uuid.uuid4()), document_id=document_id, content=buffer.strip(), chunk_index=index))
        return chunks if chunks else self._word_count_chunk(document_id, content)