import uuid
from models.document import Chunk
from config.settings import settings


class TextChunker:
    def __init__(self, chunk_size: int = None, overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP

    def chunk(self, document_id: str, content: str) -> list[Chunk]:
        words = content.split()
        chunks = []
        start = 0
        index = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
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