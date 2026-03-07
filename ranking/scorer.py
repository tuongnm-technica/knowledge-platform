from ranking.signals import semantic_signal, keyword_signal, recency_signal, popularity_signal
from config.settings import settings


class RankingScorer:
    def score(self, results: list[dict], doc_metadata: dict[str, dict]) -> list[dict]:
        scored = []
        for item in results:
            doc_id = str(item.get("document_id", ""))
            meta = doc_metadata.get(doc_id, {})

            s_sem = semantic_signal(item.get("vector_score", item.get("rrf_score", 0)))
            s_kw  = keyword_signal(item.get("keyword_score", 0))
            s_rec = recency_signal(meta.get("updated_at"))
            s_pop = popularity_signal(meta.get("click_count", 0))

            final = (
                settings.HYBRID_ALPHA      * s_sem +
                settings.BM25_WEIGHT       * s_kw  +
                settings.RECENCY_WEIGHT    * s_rec +
                settings.POPULARITY_WEIGHT * s_pop
            )

            item["final_score"] = round(final, 4)
            item["score_breakdown"] = {
                "semantic": round(s_sem, 4),
                "keyword":  round(s_kw, 4),
                "recency":  round(s_rec, 4),
                "popularity": round(s_pop, 4),
            }
            scored.append(item)

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        return scored