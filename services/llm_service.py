import asyncio
import structlog
import uuid
from typing import Any, List, Dict, Optional
from config.settings import settings
from apps.api.clients import get_llm_provider, BaseLLMProvider
from storage.db.db import AsyncSessionLocal, LLMModelORM, ModelBindingORM
from sqlalchemy import select

log = structlog.get_logger()

class LLMService:
    # Class-level semaphore to limit total concurrent LLM calls across all instances
    _semaphore = asyncio.Semaphore(getattr(settings, "MAX_CONCURRENT_LLM", 2))

    def __init__(self, model_id: Optional[str | uuid.UUID] = None, task_type: str = "chat"):
        self._provider: BaseLLMProvider = get_llm_provider()
        self._model_id = model_id
        self._task_type = task_type
        # We will resolve the actual model string and config in the chat method 
        # to ensure we have the latest DB state and handle session properly.
        self._default_model = settings.OLLAMA_LLM_MODEL

    async def _resolve_model_config(self) -> tuple[str, Dict[str, Any], Optional[str]]:
        """
        Resolves the technical model name, extra config, and API key from DB or settings.
        Returns: (model_name, config_dict, api_key)
        """
        async with AsyncSessionLocal() as session:
            if self._model_id:
                # 1. Try to fetch by ID
                try:
                    uid = uuid.UUID(str(self._model_id))
                    res = await session.execute(select(LLMModelORM).where(LLMModelORM.id == uid))
                    model_obj = res.scalar_one_or_none()
                    if model_obj and model_obj.is_active:
                        return model_obj.llm_model_name, model_obj.config or {}, model_obj.api_key
                except ValueError:
                    pass

            # 2. Try to fetch by Task Type Binding
            if self._task_type:
                res = await session.execute(
                    select(LLMModelORM)
                    .join(ModelBindingORM, ModelBindingORM.model_id == LLMModelORM.id)
                    .where(ModelBindingORM.task_type == self._task_type, LLMModelORM.is_active == True)
                    .limit(1)
                )
                model_obj = res.scalar_one_or_none()
                if model_obj:
                    return model_obj.llm_model_name, model_obj.config or {}, model_obj.api_key

            # 3. Fall back to system default from DB
            res = await session.execute(select(LLMModelORM).where(LLMModelORM.is_default == True, LLMModelORM.is_active == True).limit(1))
            model_obj = res.scalar_one_or_none()
            if model_obj:
                return model_obj.llm_model_name, model_obj.config or {}, model_obj.api_key

        # 3. Ultimate fallback to settings
        return self._default_model, {}, None

    async def chat(self, system: str, user: str, max_tokens: int = 800, on_token: Any = None, **kwargs: Any) -> str:
        """
        Gửi request chat tới LLM Provider hiện tại với cơ chế kiểm soát hàng đợi (Semaphore).
        """
        async with self._semaphore:
            try:
                # Resolve model name and config dynamically
                model_name, base_config, api_key = await self._resolve_model_config()
                
                # Override with kwargs if provided
                target_model = kwargs.get("model") or model_name
                
                # Chuẩn bị tin nhắn
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
                
                # Xử lý input đặc biệt (ví dụ: images)
                if "images" in kwargs and kwargs["images"]:
                    messages[1]["images"] = kwargs["images"]

                # Merge configs
                options = {"num_predict": max_tokens, "temperature": 0.1}
                options.update(base_config)
                if "options" in kwargs:
                    options.update(kwargs["options"])

                return await self._provider.chat(
                    model=target_model,
                    messages=messages,
                    options=options,
                    timeout=kwargs.get("timeout") or settings.LLM_TIMEOUT,
                    on_token=on_token,
                    api_key=api_key # Pass API key if needed
                )
            except asyncio.TimeoutError:
                log.warning("llm.timeout", model=self._model_id or "default")
                raise
            except Exception as e:
                log.error("llm.error", error=str(e), model=self._model_id or "default")
                raise
