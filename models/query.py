from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchQuery:
    raw: str
    rewritten: Optional[str] = None
    user_id: str = ""
    limit: int = 10
    offset: int = 0
    entities: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)

    @property
    def effective(self) -> str:
        return self.rewritten or self.raw


@dataclass
class SearchResult:
    document_id: str
    chunk_id: str
    title: str
    content: str
    url: str
    source: str
    author: str
    score: float
    score_breakdown: dict = field(default_factory=dict)
