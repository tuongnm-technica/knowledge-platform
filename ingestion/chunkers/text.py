from typing import List, Any, Dict
from .base import BaseChunker

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

class TextChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        if HAS_LANGCHAIN:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ".", "!", "?", " ", ""]
            )
        else:
            self.splitter = None

    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản thô (raw text) hoặc tài liệu chung thành các chunk.
        """
        if not text or not text.strip():
            return []
            
        if self.splitter:
            chunks = self.splitter.split_text(text)
        else:
            # Simple fallback: split by roughly fixed character counts
            # (Note: In a production environment, we should make sure LangChain is installed)
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunks.append(text[i : i + self.chunk_size])
            
        return [
            {"text": chunk_text, "metadata": {"source": kwargs.get("source", "text")}}
            for chunk_text in chunks
        ]