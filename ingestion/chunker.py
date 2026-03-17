from __future__ import annotations

from models.document import Chunk, SourceType
from .chunker_factory import get_chunker_for_source


def chunk_document(
    source_type: SourceType,
    document_id: str,
    **kwargs,
) -> list[Chunk]:
    """
    Dynamically selects and runs the appropriate chunking strategy
    based on the document's source type.

    Args:
        source_type: The type of the document source.
        document_id: The ID of the document.
        **kwargs: Source-specific data required for chunking,
                  e.g., `content` for most, `sections` for Confluence.

    Returns:
        A list of Chunk objects.
    """
    chunker = get_chunker_for_source(source_type)
    return chunker.chunk(document_id, **kwargs)
