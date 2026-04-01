from models.query import SearchQuery, SearchResult

def test_search_query_effective():
    q = SearchQuery(raw="hello")
    assert q.effective == "hello"
    
    q.rewritten = "hi"
    assert q.effective == "hi"

def test_search_result_instantiation():
    res = SearchResult(
        document_id="doc1",
        chunk_id="chunk1",
        title="Title",
        content="Content",
        url="http://url",
        source="slack",
        author="Alice",
        score=0.9
    )
    assert res.score == 0.9
    assert res.score_breakdown == {}
