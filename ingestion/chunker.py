import re
import uuid
from models.document import Chunk
from config.settings import settings


class TextChunker:
    """
    Smart chunker — strategy khác nhau theo source type:

    - Confluence : semantic (theo heading h1-h4) — đã có từ trước
    - Slack      : theo conversation thread / time window
    - Jira       : theo section (summary, description, comments)
    - File Server: paragraph-aware (không cắt giữa đoạn)
    - Default    : word-count với overlap
    """

    def __init__(self, chunk_size: int = None, overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE    # default 400
        self.overlap    = overlap    or settings.CHUNK_OVERLAP # default 50

    # ─── Public entry points ──────────────────────────────────────────────────

    def chunk(self, document_id: str, content: str) -> list[Chunk]:
        """Default: word-count chunking với overlap"""
        return self._word_count_chunk(document_id, content)

    def chunk_by_sections(self, document_id: str, sections: list[dict], *, doc_title: str = "") -> list[Chunk]:
        """Confluence semantic chunking theo heading path."""
        chunks: list[Chunk] = []
        chunk_index = 0

        for section in sections:
            title = (section.get("title") or "").strip()
            text = (section.get("content") or "").strip()
            if not text:
                continue

            header_parts = []
            if doc_title:
                header_parts.append(doc_title.strip())
            if title:
                header_parts.append(title)
            header = "\n\n".join(header_parts).strip()

            full = f"{header}\n\n{text}" if header else text

            sub = self._word_count_chunk(document_id, full, start_index=chunk_index)
            chunks.extend(sub)
            chunk_index += len(sub)

        return chunks

    def chunk_slack(self, document_id: str, content: str) -> list[Chunk]:
        """
        Slack chunking: mỗi chunk là 1 conversation window ~10-15 tin nhắn.
        Tách theo dòng [HH:MM], giữ context liên tục.
        """
        lines   = content.split("\n")
        chunks  = []
        window  = []
        index   = 0
        msg_count = 0

        for line in lines:
            window.append(line)
            # Đếm số tin nhắn (dòng bắt đầu bằng [HH:MM])
            if re.match(r"^\[\d{2}:\d{2}", line):
                msg_count += 1

            # Mỗi chunk ~12 tin nhắn
            if msg_count >= 12:
                chunk_text = "\n".join(window).strip()
                if chunk_text:
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        content=chunk_text,
                        chunk_index=index,
                    ))
                    index += 1
                    # Overlap: giữ lại 3 tin nhắn cuối làm context
                    overlap_lines = self._last_n_messages(window, n=3)
                    window    = overlap_lines
                    msg_count = len([l for l in overlap_lines if re.match(r"^\[\d{2}:\d{2}", l)])

        # Phần còn lại
        if window:
            chunk_text = "\n".join(window).strip()
            if len(chunk_text) > 30:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=chunk_text,
                    chunk_index=index,
                ))

        return chunks if chunks else self._word_count_chunk(document_id, content)

    def chunk_jira(self, document_id: str, content: str) -> list[Chunk]:
        """
        Jira chunking: tách theo double newline (paragraph).
        Summary luôn được prepend vào mỗi chunk.
        """
        content = (content or "").strip()
        if not content:
            return []

        # Nếu content ngắn thì 1 chunk
        if len(content.split()) <= self.chunk_size:
            return [
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=content,
                    chunk_index=0,
                )
            ]

        # Prefer "## Heading" sections if present (JiraConnector formats content this way).
        if "\n## " in content or content.lstrip().startswith("## "):
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
                section_text = "\n\n".join([preamble, title, body]).strip() if preamble else "\n\n".join([title, body]).strip()
                sub = self._word_count_chunk(document_id, section_text, start_index=chunk_index)
                chunks.extend(sub)
                chunk_index += len(sub)

            return chunks if chunks else self._word_count_chunk(document_id, content)

        # Fallback: paragraph chunking (legacy).
        paragraphs = re.split(r"\n{2,}", content)
        chunks: list[Chunk] = []
        buffer = ""
        index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = buffer + "\n\n" + para if buffer else para
            if len(candidate.split()) > self.chunk_size and buffer:
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        content=buffer.strip(),
                        chunk_index=index,
                    )
                )
                index += 1
                buffer = para
            else:
                buffer = candidate

        if buffer.strip():
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=buffer.strip(),
                    chunk_index=index,
                )
            )

        return chunks if chunks else self._word_count_chunk(document_id, content)

    def chunk_file(self, document_id: str, content: str) -> list[Chunk]:
        """
        File Server chunking: paragraph-aware.
        Không cắt giữa đoạn văn, giữ nguyên structure.
        """
        paragraphs = re.split(r"\n{2,}", content)
        chunks     = []
        buffer     = ""
        index      = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            candidate = buffer + "\n\n" + para if buffer else para
            if len(candidate.split()) > self.chunk_size and buffer:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=buffer.strip(),
                    chunk_index=index,
                ))
                index  += 1
                # Overlap: lấy 1 paragraph cuối làm context
                buffer  = para
            else:
                buffer = candidate

        if buffer.strip():
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=buffer.strip(),
                chunk_index=index,
            ))

        return chunks if chunks else self._word_count_chunk(document_id, content)

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _word_count_chunk(self, document_id: str, content: str,
                          start_index: int = 0) -> list[Chunk]:
        """Word-count chunking với sliding window overlap"""
        words  = content.split()
        chunks = []
        start  = 0
        index  = start_index

        while start < len(words):
            end        = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=chunk_text,
                chunk_index=index,
            ))
            index += 1
            if end == len(words):
                break
            start = end - self.overlap

        return chunks

    def _last_n_messages(self, lines: list[str], n: int) -> list[str]:
        """Lấy n tin nhắn cuối cùng từ window (dùng cho Slack overlap)"""
        result  = []
        count   = 0
        for line in reversed(lines):
            result.insert(0, line)
            if re.match(r"^\[\d{2}:\d{2}", line):
                count += 1
            if count >= n:
                break
        return result
