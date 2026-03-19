from ranking.signals import (
    graph_signal,
    keyword_signal,
    popularity_signal,
    recency_signal,
    semantic_signal,
)
from config.settings import settings

SOURCE_WEIGHTS = {
    "confluence": 1.0,
    "jira": 0.9,
    "file_server": 0.8,
    "files": 0.8,
    "slack": 0.4,
}

class RankingScorer:
    def score(self, results: list[dict], doc_metadata: dict[str, dict]) -> list[dict]:

        scored = []

        for item in results:

            doc_id = str(item.get("document_id", ""))
            meta = doc_metadata.get(doc_id, {})

            source = meta.get("source", "").lower()
            source_weight = SOURCE_WEIGHTS.get(source, 0.7)

            title = meta.get("title", "")
            query = item.get("query", "")

            s_sem = semantic_signal(item.get("vector_score", item.get("rrf_score", 0)))
            s_kw  = keyword_signal(item.get("keyword_score", 0))
            s_graph = graph_signal(item.get("graph_score", 0))
            s_rec = recency_signal(meta.get("updated_at"))
            s_rec = max(0.0, min(1.0, s_rec))
            s_pop = popularity_signal(meta.get("click_count", 0))

            final = (
                (settings.HYBRID_ALPHA or 0.5)      * (s_sem or 0.0) +
                (settings.BM25_WEIGHT or 0.3)       * (s_kw or 0.0)  +
                (settings.GRAPH_WEIGHT or 0.2)      * (s_graph or 0.0) +
                (settings.RECENCY_WEIGHT or 0.1)    * (s_rec or 0.0) +
                (settings.POPULARITY_WEIGHT or 0.1) * (s_pop or 0.0)
            )

            final *= source_weight

            if query and title:
                if query.lower() in title.lower():
                    final *= 1.8

            item["final_score"] = round(final, 4)

            item["score_breakdown"] = {
                "semantic": round(float(s_sem or 0), 4),
                "keyword":  round(float(s_kw or 0), 4),
                "graph": round(float(s_graph or 0), 4),
                "recency":  round(float(s_rec or 0), 4),
                "popularity": round(float(s_pop or 0), 4),
                "source_weight": float(source_weight or 0.7),
            }

            scored.append(item)

        scored.sort(key=lambda x: x["final_score"], reverse=True)

        return scored
