from enum import Enum


class QueryIntent(str, Enum):
    FACTUAL     = "factual"
    PROCEDURAL  = "procedural"
    EXPLORATORY = "exploratory"
    LOOKUP      = "lookup"


class IntentDetector:
    FACTUAL_KEYWORDS    = {"what", "who", "when", "where", "which", "define"}
    PROCEDURAL_KEYWORDS = {"how", "steps", "guide", "setup", "configure", "install"}
    LOOKUP_KEYWORDS     = {"find", "search", "show", "get", "list", "fetch"}

    def detect(self, query: str) -> QueryIntent:
        tokens = set(query.lower().split())
        if tokens & self.LOOKUP_KEYWORDS:      return QueryIntent.LOOKUP
        if tokens & self.PROCEDURAL_KEYWORDS:  return QueryIntent.PROCEDURAL
        if tokens & self.FACTUAL_KEYWORDS:     return QueryIntent.FACTUAL
        return QueryIntent.EXPLORATORY