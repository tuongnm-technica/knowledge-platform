from models.query import SearchQuery
from utils.text_utils import normalize_query


class QueryParser:
    def parse(self, raw: str, user_id: str = "", limit: int = 10) -> SearchQuery:
        raw = normalize_query(raw)
        if not raw:
            raise ValueError("Query không được để trống")
        return SearchQuery(raw=raw[:1000], user_id=user_id, limit=min(limit, 50))