from typing import List, Any, Dict
from .base import BaseChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TextChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", " ", ""]
        )

    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản thô (raw text) hoặc tài liệu chung thành các chunk.
        """
        if not text or not text.strip():
            return []
            
        chunks = self.splitter.split_text(text)
        return [
            {"text": chunk_text, "metadata": {"source": kwargs.get("source", "text")}}
            for chunk_text in chunks
        ]