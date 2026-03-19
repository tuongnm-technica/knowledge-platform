from __future__ import annotations

from models.document import SourceType
from .chunkers.base import BaseChunker
from .chunkers.default import WordCountChunker
from .chunkers.confluence import ConfluenceChunker
from .chunkers.jira import JiraChunker
from .chunkers.slack import SlackChunker
from .chunkers.file import FileChunker
from .chunkers.semantic_chunker import SemanticMarkdownChunker


# Tự động đăng ký chunker để tránh lỗi nếu một enum bị thiếu trong SourceType
# Lưu ý: Ta dùng type = Any cho value vì SemanticMarkdownChunker có thể không kế thừa BaseChunker cũ
_CHUNKERS: dict[SourceType, Any] = {}

for source_name, chunker_cls in [
    ("CONFLUENCE", SemanticMarkdownChunker), # Confluence (Wiki) rất hợp với Semantic Markdown
    ("JIRA", JiraChunker),
    ("SLACK", SlackChunker),
    ("FILE", SemanticMarkdownChunker),       # File Word/PDF sau khi qua LlamaParse cũng dùng Semantic
    ("TEXT", WordCountChunker),
]:
    if hasattr(SourceType, source_name):
        _CHUNKERS[getattr(SourceType, source_name)] = chunker_cls


def get_chunker_for_source(source_type: SourceType) -> Any:
    """Factory function to get the appropriate chunker instance."""
    chunker_class = _CHUNKERS.get(source_type, WordCountChunker)
    return chunker_class()