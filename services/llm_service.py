import asyncio
import structlog
from typing import Any, List, Dict
from config.settings import settings
from apps.api.clients import get_llm_provider, BaseLLMProvider

log = structlog.get_logger()

class LLMService:
    def __init__(self, model: str = None):
        self._provider: BaseLLMProvider = get_llm_provider()
        self._model = model or settings.OLLAMA_LLM_MODEL

    async def chat(self, system: str, user: str, max_tokens: int = 800, **kwargs: Any) -> str:
        """
        Gửi request chat tới LLM Provider hiện tại.
        Hỗ trợ các tùy chọn bổ sung như 'images' cho vision models.
        """
        try:
            # Chuẩn bị tin nhắn
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            
            # Xử lý input đặc biệt (ví dụ: images)
            if "images" in kwargs and kwargs["images"]:
                messages[1]["images"] = kwargs["images"]

            return await self._provider.chat(
                model=kwargs.get("model") or self._model,
                messages=messages,
                options={"num_predict": max_tokens, "temperature": 0.1},
                timeout=kwargs.get("timeout") or settings.LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("llm.timeout", model=self._model)
            raise
        except Exception as e:
            log.error("llm.error", error=str(e), model=self._model)
            raise

    async def is_available(self) -> bool:
        """Kiểm tra xem LLM Backend (Ollama/vLLM) có đang chạy không."""
        try:
            return await self._provider.is_available()
        except Exception:
            return False

    async def usage_stats(self) -> Dict[str, Any]:
        """Lấy thông tin sử dụng và các model khả dụng."""
        try:
            # Hiện tại Ollama provider hỗ trợ liệt kê local models
            if hasattr(self._provider, "list_models"):
                models = await self._provider.list_models()
                return {
                    "provider": "ollama",
                    "models": models,
                    "active_model": self._model
                }
            return {
                "provider": "unknown",
                "active_model": self._model
            }
        except Exception:
            return {"error": "Could not fetch usage stats"}
