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

    def __init__(self, model_id: Optional[str | uuid.UUID] = None, task_type: str = "chat", **kwargs: Any):
        self._model_id = model_id or kwargs.get("model")
        self._task_type = task_type
        self._init_kwargs = kwargs
        # Default model based on task type
        if task_type == "embedding":
            self._default_model = settings.OLLAMA_EMBED_MODEL
        elif task_type == "vision":
            self._default_model = settings.OLLAMA_VISION_MODEL or "llava-phi3"
        else:
            self._default_model = settings.OLLAMA_LLM_MODEL


    async def is_available(self) -> bool:
        """
        Kiểm tra xem LLM Provider mặc định có đang hoạt động hay không.
        """
        try:
            model_name, _, _, provider, base_url = await self._resolve_model_config()
            provider_client = get_llm_provider(provider, base_url)
            
            # Simple embedding check
            await provider_client.embed(model=model_name, input="ping", timeout=5)
            return True
        except Exception as e:
            log.warning("llm.availability_check.failed", error=str(e))
            return False

    async def _resolve_model_config(self) -> tuple[str, Dict[str, Any], Optional[str], str, Optional[str]]:
        """
        Resolves model metadata.
        Returns: (model_name, config_dict, api_key, provider, base_url)
        """
        async with AsyncSessionLocal() as session:
            if self._model_id:
                # 1. Try to fetch by ID
                try:
                    uid = uuid.UUID(str(self._model_id))
                    res = await session.execute(select(LLMModelORM).where(LLMModelORM.id == uid))
                    model_obj = res.scalar_one_or_none()
                    if model_obj and model_obj.is_active:
                        return (
                            model_obj.llm_model_name, 
                            model_obj.config or {}, 
                            model_obj.api_key, 
                            model_obj.provider, 
                            model_obj.base_url
                        )
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
                    return (
                        model_obj.llm_model_name, 
                        model_obj.config or {}, 
                        model_obj.api_key, 
                        model_obj.provider, 
                        model_obj.base_url
                    )

            # 3. Fall back to system default from DB
            res = await session.execute(select(LLMModelORM).where(LLMModelORM.is_default == True, LLMModelORM.is_active == True).limit(1))
            model_obj = res.scalar_one_or_none()
            if model_obj:
                return (
                    model_obj.llm_model_name, 
                    model_obj.config or {}, 
                    model_obj.api_key, 
                    model_obj.provider, 
                    model_obj.base_url
                )

        # 4. Ultimate fallback to settings
        return self._default_model, {}, None, settings.LLM_PROVIDER, settings.OLLAMA_BASE_URL

    async def chat(self, system: str, user: str, max_tokens: int = 800, on_token: Any = None, **kwargs: Any) -> str:
        """
        Gửi request chat tới LLM Provider hiện tại với cơ chế kiểm soát hàng đợi (Semaphore).
        """
        async with self._semaphore:
            try:
                # Resolve model name and config dynamically
                model_name, base_config, api_key, provider, base_url = await self._resolve_model_config()
                
                # Get dynamic provider client
                provider_client = get_llm_provider(provider, base_url)
                
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

                return await provider_client.chat(
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

    async def embed(self, input_text: str | List[str], **kwargs: Any) -> List[float] | List[List[float]]:
        """
        Gửi request embedding tới LLM Provider hiện tại.
        """
        async with self._semaphore:
            try:
                # Resolve model name and config dynamically
                model_name, _, api_key, provider, base_url = await self._resolve_model_config()
                
                # Get dynamic provider client
                provider_client = get_llm_provider(provider, base_url)
                
                # Override with kwargs if provided
                target_model = kwargs.get("model") or model_name
                
                return await provider_client.embed(
                    model=target_model,
                    input=input_text,
                    timeout=kwargs.get("timeout") or settings.LLM_TIMEOUT * 2
                )
            except Exception as e:
                log.error("llm.embed.error", error=str(e), model=self._model_id or "default")
                raise
