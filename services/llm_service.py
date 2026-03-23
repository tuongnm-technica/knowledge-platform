import asyncio
import structlog
from typing import Any, List, Dict
from config.settings import settings
from apps.api.clients import get_llm_provider, BaseLLMProvider

log = structlog.get_logger()

class LLMService:
    # Class-level semaphore to limit total concurrent LLM calls across all instances
    _semaphore = asyncio.Semaphore(getattr(settings, "MAX_CONCURRENT_LLM", 2))

    def __init__(self, model: str = None):
        self._provider: BaseLLMProvider = get_llm_provider()
        self._model = model or settings.OLLAMA_LLM_MODEL

    async def chat(self, system: str, user: str, max_tokens: int = 800, on_token: Any = None, **kwargs: Any) -> str:
        """
        Gửi request chat tới LLM Provider hiện tại với cơ chế kiểm soát hàng đợi (Semaphore).
        """
        async with self._semaphore:
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
                on_token=on_token,
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
