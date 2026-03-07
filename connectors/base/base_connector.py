from abc import ABC, abstractmethod
from models.document import Document


class BaseConnector(ABC):

    @abstractmethod
    async def fetch_documents(self) -> list[Document]:
        ...

    @abstractmethod
    async def get_permissions(self, source_id: str) -> list[str]:
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        ...