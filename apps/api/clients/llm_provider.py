from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict

class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM inference providers.
    """

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Send a chat request to the LLM.
        """
        pass

    @abstractmethod
    async def embed(
        self,
        model: str,
        input: str | List[str],
        timeout: Optional[float] = None,
    ) -> List[float] | List[List[float]]:
        """
        Generate embeddings for the input text.
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the service is healthy and reachable.
        """
        pass
