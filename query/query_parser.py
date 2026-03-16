from graph.entity_extractor import EntityExtractor
from models.query import SearchQuery
from utils.text_utils import normalize_query


class QueryParser:
    def __init__(self):
        self._entities = EntityExtractor()

    def parse(self, raw: str, user_id: str = "", limit: int = 10) -> SearchQuery:
        raw = normalize_query(raw)
        if not raw:
            raise ValueError("Query khong duoc de trong")

        query_text = raw[:1000]
        entities = [entity.name for entity in self._entities.extract_typed(query_text)]
        if not entities:
            entities = [query_text]
        return SearchQuery(
            raw=query_text,
            user_id=user_id,
            limit=min(limit, 50),
            entities=entities,
        )
