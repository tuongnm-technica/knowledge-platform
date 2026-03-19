from .llm_provider import BaseLLMProvider
from .ollama_provider import OllamaProvider

def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider.
    """
    from config.settings import settings
    
    provider_type = str(settings.LLM_PROVIDER).lower()
    
    if provider_type == "ollama":
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
    elif provider_type == "vllm" or provider_type == "openai":
        # Placeholder: will implement VLLMProvider/OpenAIProvider logic soon
        from .ollama_provider import OllamaProvider # For now, fallback to Ollama if misconfigured
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
    else:
        # Default to Ollama for backward compatibility
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
