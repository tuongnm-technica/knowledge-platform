"""
orchestration/tools/summarize.py
Tool: summarize_document — tóm tắt 1 document dài từ knowledge base.
"""
from orchestration.tools.base import BaseTool, ToolSpec, ToolResult
from persistence.document_repository import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
import httpx
import structlog

log = structlog.get_logger()

SUMMARIZE_SYSTEM = """Bạn là assistant tóm tắt tài liệu kỹ thuật nội bộ.
Tóm tắt ngắn gọn, súc tích, giữ các điểm chính, số liệu quan trọng, và action items nếu có.
Trả lời bằng tiếng Việt. Tối đa 300 từ."""


class SummarizeDocumentTool(BaseTool):
    def __init__(self, session: AsyncSession):
        self._repo = DocumentRepository(session)
        self._base = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_LLM_MODEL

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="summarize_document",
            description=(
                "Tóm tắt nội dung của 1 tài liệu cụ thể. "
                "Dùng khi user muốn tóm tắt 1 page Confluence, Jira issue, hoặc file."
            ),
            parameters={
                "document_id": "ID của document cần tóm tắt (lấy từ kết quả search_knowledge)",
                "focus":       "Chủ đề cần tập trung (tuỳ chọn, ví dụ: 'action items', 'technical decisions')",
            },
        )

    async def run(self, document_id: str, focus: str = "", **_) -> ToolResult:
        try:
            rows = await self._repo.get_by_ids([document_id])
            if not rows:
                return ToolResult(success=False, data={}, summary="",
                                  error=f"Không tìm thấy document: {document_id}")

            doc     = rows[0]
            content = doc.get("content", "")[:3000]  # limit để LLM không bị quá dài
            title   = doc.get("title", "Untitled")

            focus_hint = f"\nTập trung vào: {focus}" if focus else ""
            prompt = f"Tài liệu: {title}\n\nNội dung:\n{content}{focus_hint}\n\nTóm tắt:"

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._base}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": SUMMARIZE_SYSTEM},
                            {"role": "user",   "content": prompt},
                        ],
                        "stream": False,
                        "options": {"num_predict": 400, "temperature": 0.1},
                    }
                )
                resp.raise_for_status()
                summary_text = resp.json()["message"]["content"].strip()

            result = {"document_id": document_id, "title": title, "summary": summary_text}
            log.info("tool.summarize_document", doc_id=document_id)
            return ToolResult(success=True, data=result,
                              summary=f"Tóm tắt '{title}':\n{summary_text}")

        except Exception as e:
            log.error("tool.summarize_document.error", error=str(e))
            return ToolResult(success=False, data={}, summary="", error=str(e))