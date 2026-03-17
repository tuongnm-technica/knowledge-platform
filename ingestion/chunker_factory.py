from __future__ import annotations

from models.document import SourceType
from .chunkers.base import BaseChunker
from .chunkers.default import WordCountChunker
from .chunkers.confluence import ConfluenceChunker
from .chunkers.jira import JiraChunker
from .chunkers.slack import SlackChunker
from .chunkers.file import FileChunker


# Registry mapping source types to their specific chunker classes
_CHUNKERS: dict[SourceType, type[BaseChunker]] = {
    SourceType.CONFLUENCE: ConfluenceChunker,
    SourceType.JIRA: JiraChunker,
    SourceType.SLACK: SlackChunker,
    SourceType.FILE: FileChunker,
    # Add other source types here as you create new chunker classes
}


def get_chunker_for_source(source_type: SourceType) -> BaseChunker:
    """Factory function to get the appropriate chunker instance."""
    chunker_class = _CHUNKERS.get(source_type, WordCountChunker)
    return chunker_class()