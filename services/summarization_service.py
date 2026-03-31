import structlog
from typing import Optional
from models.document import SourceType
from services.llm_service import LLMService

log = structlog.get_logger()

class SummarizationService:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service or LLMService(task_type="ingestion_llm")

    async def summarize(self, content: str, source_type: SourceType, title: str = "") -> str:
        """
        Tạo bản tóm tắt nội dung dựa trên loại nguồn dữ liệu.
        """
        if not content or len(content.strip()) < 50:
            return ""

        if source_type == SourceType.ZOOM or source_type == SourceType.GOOGLE_MEET:
            system_prompt = (
                "Bạn là một trợ lý AI chuyên nghiệp chuyên tóm tắt các cuộc họp. "
                "Nhiệm vụ của bạn là đọc bản chép lời (transcript) và tóm tắt lại các ý chính. "
                "Hãy tập trung vào: \n"
                "1. Mục đích cuộc họp.\n"
                "2. Các quyết định quan trọng đã được thống nhất.\n"
                "3. Các đầu việc (Action Items) và người chịu trách nhiệm.\n"
                "4. Các vấn đề còn tồn đọng.\n"
                "Yêu cầu: Viết ngắn gọn, súc tích bằng Tiếng Việt, sử dụng bullet points."
            )
        elif source_type == SourceType.CONFLUENCE:
            system_prompt = (
                "Bạn là một chuyên gia phân tích tài liệu kỹ thuật. "
                "Hãy tóm tắt tài liệu Confluence này một cách súc tích. "
                "Tập trung vào: Tổng quan, Mục tiêu kỹ thuật, và các Kết luận quan trọng. "
                "Yêu cầu: Viết bằng Tiếng Việt, tối đa 3-5 câu hoặc bullet points."
            )
        else:
            system_prompt = (
                "Hãy tóm tắt nội dung sau đây một cách súc tích bằng Tiếng Việt. "
                "Giữ lại các thông tin quan trọng nhất."
            )

        user_prompt = f"Tiêu đề: {title}\n\nNội dung cần tóm tắt:\n{content[:15000]}" # Giới hạn context window cơ bản

        try:
            log.info("summarization.start", source=source_type.value, title=title)
            summary = await self._llm.chat(system=system_prompt, user=user_prompt, max_tokens=1000)
            log.info("summarization.done", source=source_type.value)
            return summary.strip()
        except Exception as e:
            log.error("summarization.failed", error=str(e), source=source_type.value)
            return ""
