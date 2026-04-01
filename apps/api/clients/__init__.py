from typing import Optional
from .llm_provider import BaseLLMProvider
from .ollama_provider import OllamaProvider

def get_llm_provider(provider_type: Optional[str] = None, base_url: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider.
    """
    from config.settings import settings
    
    p_type = str(provider_type or settings.LLM_PROVIDER).lower()
    url = base_url or settings.OLLAMA_BASE_URL
    
    if p_type == "ollama":
        return OllamaProvider(base_url=url)
    elif p_type == "vllm" or p_type == "openai":
        # Placeholder: will implement VLLMProvider/OpenAIProvider logic soon
        return OllamaProvider(base_url=url)
    else:
        # Default to Ollama for backward compatibility
        return OllamaProvider(base_url=url)
