import pytest
from datetime import datetime
from models.document import Document, SourceType
from ingestion.metadata_extractor import MetadataExtractor

@pytest.fixture
def extractor():
    return MetadataExtractor()

def test_extract_basic(extractor):
    doc = Document(
        id="test-1",
        source=SourceType.CONFLUENCE,
        source_id="src-1",
        title="Test Doc",
        content="This is a simple test document with some words.",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={"existing": "value"}
    )
    meta = extractor.extract(doc)
    
    assert meta["existing"] == "value"
    assert meta["word_count"] == 9
    assert meta["char_count"] == len(doc.content)
    assert meta["language"] == "en"

def test_extract_urls(extractor):
    doc = Document(
        id="test-2",
        source=SourceType.CONFLUENCE,
        source_id="src-2",
        title="URL Doc",
        content="Check out https://google.com and http://example.org/path ",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    meta = extractor.extract(doc)
    assert "https://google.com" in meta["extracted_urls"]
    assert "http://example.org/path" in meta["extracted_urls"]

def test_detect_vietnamese(extractor):
    doc = Document(
        id="test-3",
        source=SourceType.CONFLUENCE,
        source_id="src-3",
        title="VN Doc",
        content="Đây là một văn bản tiếng Việt có dấu để kiểm tra nhận diện ngôn ngữ.",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    meta = extractor.extract(doc)
    assert meta["language"] == "vi"

def test_detect_english_short(extractor):
    doc = Document(
        id="test-4",
        source=SourceType.CONFLUENCE,
        source_id="src-4",
        title="EN Doc",
        content="Short English text.",
        url="http://test.com",
        author="test",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    meta = extractor.extract(doc)
    assert meta["language"] == "en"
