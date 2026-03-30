import re
import uuid
from typing import List, Any, Dict
from models.document import Chunk
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

    def chunk(self, document_id: str, **kwargs) -> List[Chunk]:
        """
        Chia nhỏ văn bản thô (raw text) dựa trên Markdown Headers (Structural) -> Semantic.
        """
        text = kwargs.get("content", "")
        title = kwargs.get("title", "Document")
        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        
        if not text or not text.strip():
            return []
            
        # 1. Structural Parsing: Split by Markdown Headers (H1, H2, H3)
        # Match lines starting with '# ', '## ', etc.
        pattern = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)
        matches = list(pattern.finditer(text))
        
        sections = []
        if not matches:
            # Không có header, coi toàn bộ text là 1 section
            sections.append({"title": title, "content": text, "level": 1})
        else:
            # Có headers
            for i, match in enumerate(matches):
                level = len(match.group(1))
                sec_title = match.group(2).strip()
                start_idx = match.end()
                end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
                
                sec_content = text[start_idx:end_idx].strip()
                sections.append({"title": sec_title, "content": sec_content, "level": level})
                
            # Đoạn text trước header đầu tiên (nếu có)
            first_header_start = matches[0].start()
            if first_header_start > 0:
                pre_text = text[:first_header_start].strip()
                if pre_text:
                    sections.insert(0, {"title": "Introduction", "content": pre_text, "level": 1})

        # 2. Create Parent and Child Chunks
        chunks = []
        chunk_idx = 0
        
        for sec in sections:
            sec_title = sec["title"]
            sec_content = sec["content"]
            sec_level = sec["level"]
            
            # Tạo Parent Chunk ảo cho Section
            parent_id = str(uuid.uuid4())
            chunks.append(Chunk(
                id=parent_id,
                document_id=doc_uuid,
                content=f"Heading: {sec_title}\n\n{sec_content[:500]}...",
                chunk_index=chunk_idx,
                parent_chunk_id=None,  # Tương lai có thể link H2 -> H1
                section_title=sec_title,
                level=sec_level
            ))
            chunk_idx += 1
            
            if not sec_content:
                continue
                
            # Cắt content bên dưới thành Semantic Blocks
            if self.splitter:
                sub_texts = self.splitter.split_text(sec_content)
            else:
                sub_texts = [sec_content[i : i + self.chunk_size] for i in range(0, len(sec_content), self.chunk_size - self.chunk_overlap)]
                
            for sub_text in sub_texts:
                if not sub_text.strip(): continue
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_uuid,
                    content=sub_text,
                    chunk_index=chunk_idx,
                    parent_chunk_id=parent_id,
                    section_title=sec_title,
                    level=sec_level + 1
                ))
                chunk_idx += 1
                
        return chunks