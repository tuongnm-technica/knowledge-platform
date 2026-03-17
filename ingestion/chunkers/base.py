from abc import ABC, abstractmethod
from typing import List, Any, Dict

class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Chia nhỏ văn bản (text) thành các chunk.
        """
        pass