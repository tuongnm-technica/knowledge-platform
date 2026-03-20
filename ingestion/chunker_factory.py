from __future__ import annotations
from typing import Any

from models.document import SourceType
from .chunkers.base import BaseChunker
from .chunkers.default import WordCountChunker
from .chunkers.confluence import ConfluenceChunker
from .chunkers.jira import JiraChunker
from .chunkers.slack import SlackChunker
from .chunkers.file import FileChunker


# Tự động đăng ký chunker để tránh lỗi nếu một enum bị thiếu trong SourceType
# Lưu ý: Ta dùng type = Any cho value vì SemanticMarkdownChunker có thể không kế thừa BaseChunker cũ
_CHUNKERS: dict[SourceType, Any] = {}

for source_name, chunker_cls in [
    ("CONFLUENCE", ConfluenceChunker), 
    ("JIRA", JiraChunker),
    ("SLACK", SlackChunker),
    ("FILE_SERVER", FileChunker),       
    ("TEXT", WordCountChunker),
]:
    if hasattr(SourceType, source_name):
        _CHUNKERS[getattr(SourceType, source_name)] = chunker_cls


def get_chunker_for_source(source_type: SourceType) -> Any:
    """Factory function to get the appropriate chunker instance."""
    chunker_class = _CHUNKERS.get(source_type, WordCountChunker)
    return chunker_class()