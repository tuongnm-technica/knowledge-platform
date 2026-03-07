import re


def truncate(text: str, max_chars: int = 500, suffix: str = "...") -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)].rsplit(" ", 1)[0] + suffix


def normalize_query(query: str) -> str:
    query = query.strip().lower()
    query = re.sub(r"\s+", " ", query)
    return query