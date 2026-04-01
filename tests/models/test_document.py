from datetime import datetime
from models.document import Document, SourceType, Chunk

def test_document_to_dict():
    now = datetime.utcnow()
    doc = Document(
        id="doc1",
        source=SourceType.SLACK,
        source_id="slack1",
        title="Test Doc",
        content="Hello world",
        url="http://example.com",
        author="Alice",
        created_at=now,
        updated_at=now,
        metadata={"key": "value"},
        workspace_id="ws1"
    )
    
    d = doc.to_dict()
    assert d["id"] == "doc1"
    assert d["source"] == "slack"
    assert d["created_at"] == now.isoformat()
    assert d["metadata"] == {"key": "value"}
    assert d["workspace_id"] == "ws1"

def test_chunk_instantiation():
    chunk = Chunk(
        id="chunk1",
        document_id="doc1",
        content="chunk content",
        chunk_index=0,
        level=1
    )
    assert chunk.id == "chunk1"
    assert chunk.level == 1
    assert chunk.embedding is None
