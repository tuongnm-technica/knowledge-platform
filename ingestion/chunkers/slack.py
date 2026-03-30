import uuid
import re
from typing import List
from models.document import Chunk
from .base import BaseChunker

class SlackChunker(BaseChunker):
    def chunk(self, document_id: str, **kwargs) -> List[Chunk]:
        """
        Chia nhỏ văn bản từ Slack thành các chunk theo cấu trúc:
        - Level 1 Parent: Chunk đại diện cho cả Ngày (Day).
        - Level 2: Từng đoạn hội thoại/Message trỏ về Level 1.
        """
        text = kwargs.get("content", "")
        title = kwargs.get("title", "Slack Conversation")
        if not text:
            return []

        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        
        # 1. Tạo Level 1 Parent Chunk (Ngày)
        parent_id = str(uuid.uuid4())
        parent_chunk = Chunk(
            id=parent_id,
            document_id=doc_uuid,
            content=f"Summary of {title}\n{text[:500]}...", # Trích 1 phần làm đại diện
            chunk_index=0,
            parent_chunk_id=None,
            section_title=title,
            level=1
        )
        
        chunks = [parent_chunk]
        chunk_idx = 1
        
        # 2. Parse từng message (dạng [HH:MM|ts] Sender: Text)
        # Tách dựa vào pattern bắt đầu line
        message_blocks = re.split(r'\n(?=\[\d{2}:\d{2}(?:\|[^\]]+)?\] )', text)
        
        for block in message_blocks:
            block = block.strip()
            if not block or block.startswith("==="): # Bỏ qua header
                continue
                
            # Tạo chunk cho message này
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_uuid,
                content=block,
                chunk_index=chunk_idx,
                parent_chunk_id=parent_id,
                section_title="Message",
                level=2
            ))
            chunk_idx += 1
            
        return chunks