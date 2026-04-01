import pytest
import uuid
from models.document import SourceType, Chunk
from ingestion.chunker import chunk_document
from ingestion.chunker_factory import get_chunker_for_source
from ingestion.chunkers.default import WordCountChunker

from ingestion.chunkers.confluence import ConfluenceChunker
from ingestion.chunkers.jira import JiraChunker

def test_get_chunker_factory():
    # Test mapping
    assert isinstance(get_chunker_for_source(SourceType.CONFLUENCE), ConfluenceChunker)
    assert isinstance(get_chunker_for_source(SourceType.JIRA), JiraChunker) 

def test_chunk_document_delegation(mocker):
    # Mock the chunker returned by the factory
    mock_chunker = mocker.Mock()
    mock_chunker.chunk.return_value = [Chunk(id=str(uuid.uuid4()), document_id=uuid.uuid4(), content="test", chunk_index=0)]
    
    mocker.patch("ingestion.chunker.get_chunker_for_source", return_value=mock_chunker)
    
    doc_id = str(uuid.uuid4())
    result = chunk_document(SourceType.CONFLUENCE, doc_id, content="some content")
    
    assert len(result) == 1
    mock_chunker.chunk.assert_called_once_with(doc_id, content="some content")

def test_word_count_chunker_basic():
    chunker = WordCountChunker()
    doc_id = str(uuid.uuid4())
    
    # Text with 10 words
    content = "one two three four five six seven eight nine ten"
    
    # Test with small chunk size for testing
    # We can't easily pass chunk_size to WordCountChunker.chunk because it uses default
    # But we can test the internal _word_count_chunk
    chunks = chunker._word_count_chunk(doc_id, content, chunk_size=5, chunk_overlap=2)
    
    # Expected:
    # 1: one two three four five (index 0)
    # 2: four five six seven eight (index 1) - overlap 2 words
    # 3: seven eight nine ten (index 2) - overlap 2 words
    
    assert len(chunks) == 3
    assert chunks[0].content == "one two three four five"
    assert chunks[1].content == "four five six seven eight"
    assert chunks[2].content == "seven eight nine ten"
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2

def test_word_count_chunker_empty():
    chunker = WordCountChunker()
    chunks = chunker.chunk(str(uuid.uuid4()), content="")
    assert chunks == []
