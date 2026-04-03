import json
import re
import asyncio
import structlog
from typing import List, Dict, Any
from config.settings import settings
from services.llm_service import LLMService

log = structlog.get_logger()

class SemanticRelationExtractor:
    """
    Sử dụng LLM nhỏ (Llama 3, Qwen) để đọc Text Chunk và trích xuất Quan hệ ngữ nghĩa.
    Thay thế cho cơ chế Co-occurrence tự động trước đây.
    """
    def __init__(self):
        # We reuse OllamaLLM to perform local fast extraction.
        # It's recommended to set LLM_MODEL in settings to a fast 8B model.
        self._llm = LLMService(task_type="extraction")
        self._allowed_predicates = [
            "depends_on",
            "part_of",
            "causes",
            "triggers",
            "implements"
        ]

    async def extract(self, text: str) -> List[Dict[str, str]]:
        """
        Trích xuất mảng SPO từ văn bản thô.
        """
        if not text or len(text.strip()) < 20:
            return []

        # Giới hạn text length để tránh nghẽn model nhỏ.
        # Ở môi trường production thật, TextCleaner đã xử lý, 
        # nhưng ta lấy 3000 ký tự đầu tiên để extract context xương sống.
        safe_text = text[:3000]

        sys_prompt = f"""
Bạn là chuyên gia Phân tích Dữ liệu và Đồ thị Tri thức (Knowledge Graph Data Engineer).
Nhiệm vụ của bạn là đọc đoạn văn bản cung cấp và trích xuất các Mối Quan Hệ (Relations) giữa các Hệ thống, Tính năng, Khái niệm, hoặc Người dùng.

YÊU CẦU BẮT BUỘC:
1. Trả về DUY NHẤT một mảng JSON các object chứa ba trường: 'subject', 'predicate', 'object'.
2. TRƯỜNG 'predicate' CHỈ ĐƯỢC PHÉP CHỌN 1 TRONG CÁC TỪ SAU ĐÂY:
{", ".join(self._allowed_predicates)}
3. Chủ ngữ (subject) và Tân ngữ (object) phải là Cụm Danh Từ (Noun Phrase) rõ ràng (Ví dụ: "Microservice Auth", "Database Users", "Chức năng Thanh toán").
4. Trả về mảng JSON hợp lệ, KHÔNG GIẢI THÍCH THÊM.

Ví dụ:
[
  {{"subject": "Chức năng Đăng nhập", "predicate": "depends_on", "object": "Dịch vụ Auth"}},
  {{"subject": "Nút Thanh toán", "predicate": "triggers", "object": "Luồng tính tiền"}}
]
"""

        try:
            # max_tokens=300 là đủ cho một list json ngắn
            raw_response = await self._llm.chat(sys_prompt, safe_text, max_tokens=300)
            
            # Xử lý trường hợp LLM bọc kết quả trong markdown ```json ... ```
            cleaned_response = raw_response.strip()
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json").split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].split("```").strip()

            # Trích xuất mảng JSON bằng regex để loại bỏ các text dư thừa ở đầu/cuối
            match = re.search(r"\[.*\]", cleaned_response, re.DOTALL)
            if match:
                json_str = match.group(0)
                relations = json.loads(json_str)
                
                # Normalize and validate
                valid_relations = []
                for rel in relations:
                    s = rel.get("subject", "").strip()
                    p = rel.get("predicate", "").strip().lower()
                    o = rel.get("object", "").strip()
                    
                    if s and o and p in self._allowed_predicates:
                        # Avoid self-loops
                        if s.lower() != o.lower():
                            valid_relations.append({"subject": s, "predicate": p, "object": o})
                
                log.info("relation_extractor.success", 
                         found=len(valid_relations), 
                         text_length=len(safe_text))
                return valid_relations
                
            return []
            
        except json.JSONDecodeError:
            log.warning("relation_extractor.json_parse_error", raw=raw_response[:100])
            return []
        except Exception as e:
            log.error("relation_extractor.failed", error=str(e))
            return []
