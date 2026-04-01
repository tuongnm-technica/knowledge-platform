from utils.text_utils import truncate, normalize_query

def test_truncate():
    text = "The quick brown fox jumps over the lazy dog"
    # Basic truncation
    assert truncate(text, 20) == "The quick brown..."
    # Exact length
    assert truncate(text, len(text)) == text
    # Short text
    assert truncate("Hello", 10) == "Hello"
    # Truncate at space
    assert truncate("VeryLongWord", 5) == "Ve..."
    # Suffix length check
    assert truncate("Test text", 5, suffix=".") == "Test."

def test_normalize_query():
    assert normalize_query("  Hello   World  ") == "hello world"
    assert normalize_query("\nLine break \t tab") == "line break tab"
    assert normalize_query("UPPER CASE") == "upper case"
    assert normalize_query("") == ""
