import uuid
from models.document import Chunk
from config.settings import settings


class TextChunker:

    def __init__(self, chunk_size: int = None, overlap: int = None):
        self.chunk_size = chunk_size or getattr(settings, "CHUNK_SIZE", 400)
        self.overlap    = overlap    or getattr(settings, "CHUNK_OVERLAP", 50)

    def chunk(self, document_id: str, content: str) -> list[Chunk]:
        """Fallback — chunk theo word count. Dùng cho Jira + Slack."""
        words  = content.split()
        chunks = []
        start  = 0
        index  = 0

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

    def chunk_by_sections(self, document_id: str, sections: list[dict]) -> list[Chunk]:
        """
        Semantic chunking theo sections — dùng cho Confluence.
        Mỗi section = 1 chunk. Section quá dài thì chia nhỏ nhưng giữ title.
        """
        chunks = []
        index  = 0

        for section in sections:
            title   = section.get("title", "")
            content = section.get("content", "")

            # Ghép title vào đầu content để giữ ngữ cảnh
            full_text = f"{title}\n\n{content}".strip() if title else content.strip()
            if not full_text:
                continue

            words = full_text.split()

            if len(words) <= self.chunk_size:
                # Section ngắn → 1 chunk
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=full_text,
                    chunk_index=index,
                ))
                index += 1
            else:
                # Section dài → chia nhỏ, giữ title ở mỗi chunk
                start = 0
                while start < len(words):
                    end        = min(start + self.chunk_size, len(words))
                    body       = " ".join(words[start:end])
                    chunk_text = f"{title}\n\n{body}" if title else body

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