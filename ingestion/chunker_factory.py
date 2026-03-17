from __future__ import annotations

from models.document import SourceType
from .chunkers.base import BaseChunker
from .chunkers.default import WordCountChunker
from .chunkers.confluence import ConfluenceChunker
from .chunkers.jira import JiraChunker
from .chunkers.slack import SlackChunker
from .chunkers.file import FileChunker


# Tự động đăng ký chunker để tránh lỗi nếu một enum bị thiếu trong SourceType
_CHUNKERS: dict[SourceType, type[BaseChunker]] = {}

for source_name, chunker_cls in [
    ("CONFLUENCE", ConfluenceChunker),
    ("JIRA", JiraChunker),
    ("SLACK", SlackChunker),
    ("FILE", FileChunker),
]:
    if hasattr(SourceType, source_name):
        _CHUNKERS[getattr(SourceType, source_name)] = chunker_cls


def get_chunker_for_source(source_type: SourceType) -> BaseChunker:
    """Factory function to get the appropriate chunker instance."""
    chunker_class = _CHUNKERS.get(source_type, WordCountChunker)
    return chunker_class()