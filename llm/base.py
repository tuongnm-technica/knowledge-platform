from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class ILLMClient(ABC):
    """Abstract base class for a Large Language Model client."""

    @abstractmethod
    async def chat(self, system: str, user: str, max_tokens: int = 400, **kwargs: Any) -> str:
        """
        Generates a chat completion.

        Args:
            system: The system prompt.
            user: The user prompt.
            **kwargs: Additional provider-specific arguments (e.g., model, images).

        Returns:
            The generated text content.
        """
        raise NotImplementedError