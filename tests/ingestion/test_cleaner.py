import pytest
from ingestion.cleaner import TextCleaner

@pytest.fixture
def cleaner():
    return TextCleaner()

def test_clean_basic(cleaner):
    text = "  Hello   World  "
    assert cleaner.clean(text) == "Hello World"

def test_clean_html(cleaner):
    text = "<div>Hello <b>World</b></div>"
    # _remove_html replaces tags with space, then _normalize_whitespace cleans it up
    assert cleaner.clean(text) == "Hello World"

def test_clean_script_style(cleaner):
    text = "<script>alert('hi')</script><style>body{}</style>Hello"
    assert cleaner.clean(text) == "Hello"

def test_clean_whitespace_normalization(cleaner):
    text = "Lines\n\n\n\nwith\n\nbreaks"
    # \n{3,} -> \n\n
    assert cleaner.clean(text) == "Lines\n\nwith\n\nbreaks"

def test_clean_complex_integration(cleaner):
    text = """
    <script>var x = 1;</script>
    <div class="test">
        <h1>Title</h1>
        <p>This is a   test with <b>bold</b> text.</p>
    </div>
    """
    cleaned = cleaner.clean(text)
    assert "Title" in cleaned
    assert "This is a test with bold text." in cleaned
    assert "var x = 1;" not in cleaned
