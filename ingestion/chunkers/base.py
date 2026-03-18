import uuid
from abc import ABC, abstractmethod
from typing import List, Any, Dict
from models.document import Chunk


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, document_id: str, **kwargs) -> List[Chunk]:
        """
        Chia nhỏ văn bản thành các chunk.
        """
        pass

    def _word_count_chunk(
        self, 
        document_id: str, 
        text: str, 
        chunk_size: int = 500, 
        chunk_overlap: int = 50
    ) -> List[Chunk]:
        """
        Helper method to perform word-count based chunking with overlap.
        """
        if not text:
            return []
            
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i : i + chunk_size]
            content = " ".join(chunk_words)
            
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=uuid.UUID(document_id) if isinstance(document_id, str) else document_id,
                content=content,
                chunk_index=len(chunks)
            ))
            
            if i + chunk_size >= len(words):
                break
                
        return chunks