from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class SourceType(str, Enum):
    SLACK = "slack"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    GOOGLE_DRIVE = "google_drive"
    FILE_SERVER  = "file_server"


@dataclass
class Document:
    id: str
    source: SourceType
    source_id: str
    title: str
    content: str
    url: str
    author: str
    created_at: datetime
    updated_at: datetime
    metadata: dict = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "permissions": self.permissions,
            "entities": self.entities,
        }


@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    chunk_index: int
    embedding: Optional[list[float]] = None