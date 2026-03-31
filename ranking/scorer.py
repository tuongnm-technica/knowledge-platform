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
    def score(self, results: list[dict], doc_metadata: dict[str, dict], intent: str = "general") -> list[dict]:

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

            # Hybrid Architecture Fusion Score: 
            # 0.5 * Vector (Semantic) + 0.3 * Graph + 0.2 * Metadata (Keyword)
            vector_fusion = float(s_sem or 0.0)
            graph_fusion = float(s_graph or 0.0)
            metadata_fusion = float(s_kw or 0.0)

            # Dynamic Context Scoring based on query intent
            if intent in ["flow", "dependency", "architecture"]:
                # High graph dependency
                w_v, w_g, w_m = 0.4, 0.4, 0.2
            elif intent == "fact":
                # Factual lookup
                w_v, w_g, w_m = 0.7, 0.1, 0.2
            else:
                # Default (General)
                w_v, w_g, w_m = 0.5, 0.3, 0.2

            final = (w_v * vector_fusion) + (w_g * graph_fusion) + (w_m * metadata_fusion)
            
            # Add small bumps for recency and popularity
            final += (0.05 * (s_rec or 0.0)) + (0.05 * (s_pop or 0.0))

            final *= float(source_weight or 1.0)

            if query and title:
                if query.lower() in title.lower():
                    # Additive bonus instead of extreme multiplier (1.8x was too much)
                    final += 0.15

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
