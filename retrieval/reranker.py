"""
retrieval/reranker.py
──────────────────────
LLM-based reranker cho kết quả search.

Flow:
    Hybrid search → top 20 candidates
    → Reranker (LLM đánh giá relevance)
    → top 5 kết quả chất lượng cao

Tại sao cần:
    - Vector search có recall tốt nhưng precision thấp
    - LLM reranker hiểu ngữ nghĩa sâu hơn cosine similarity

Optimization:
    - Chỉ rerank top 15
    - Batch scoring (1 LLM call)
    - Cache theo (query, chunk_ids)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import httpx
import structlog

from config.settings import settings

log = structlog.get_logger()

# ─────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────

_rerank_cache: dict[str, tuple[list[dict], float]] = {}

_CACHE_TTL = 120

SHORT_ID_LEN = 12
MAX_CHARS = 500


# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────

RERANK_SYSTEM = """
Bạn là chuyên gia đánh giá mức độ liên quan của tài liệu kỹ thuật.

Nhiệm vụ:
Cho điểm mức độ liên quan giữa câu hỏi và từng đoạn văn bản.

Thang điểm:
3 = Trả lời trực tiếp câu hỏi
2 = Có thông tin liên quan
1 = Chỉ liên quan gián tiếp
0 = Không liên quan

Quy tắc:
- Chỉ đánh giá dựa trên nội dung đoạn văn
- Không suy diễn ngoài nội dung
- Không giải thích

Chỉ trả JSON:

{"scores":[{"id":"chunk_id","score":3}]}
"""


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

async def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank candidates theo relevance với query.

    candidates: list[dict] có keys:
        chunk_id
        content
        title
        rrf_score / final_score
    """

    if not candidates:
        return []

    if len(candidates) <= top_k:
        return candidates

    # ─────────────────────────
    # Cache check
    # ─────────────────────────

    cache_key = _make_cache_key(query, candidates[:15])

    if cache_key in _rerank_cache:
        results, ts = _rerank_cache[cache_key]

        if time.time() - ts < _CACHE_TTL:
            log.debug("reranker.cache_hit", query=query[:60])
            return results

    # ─────────────────────────
    # Chỉ rerank top 15
    # ─────────────────────────

    to_rerank = candidates[:15]
    rest = candidates[15:]

    try:

        scores = await _llm_score(query, to_rerank)

        # build score map
        score_map = {
            s["id"][:SHORT_ID_LEN]: s["score"]
            for s in scores
        }

        # normalize original score
        orig_scores = [
            c.get("final_score", c.get("rrf_score", 0))
            for c in to_rerank
        ]

        max_orig = max(orig_scores) or 1

        for c in to_rerank:

            cid = str(c.get("chunk_id", ""))[:SHORT_ID_LEN]

            llm_score = score_map.get(cid, 1)

            original = c.get("final_score", c.get("rrf_score", 0))
            norm_orig = original / max_orig

            c["llm_relevance"] = llm_score

            c["rerank_score"] = round(
                0.6 * (llm_score / 3.0)
                + 0.4 * norm_orig,
                4
            )

        reranked = sorted(
            to_rerank,
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        result = (reranked + rest)[:top_k]

        _rerank_cache[cache_key] = (result, time.time())

        log.info(
            "reranker.done",
            query=query[:60],
            candidates=len(to_rerank),
            top_k=top_k
        )

        return result

    except Exception as e:

        log.warning("reranker.failed", error=str(e))

        return candidates[:top_k]


# ─────────────────────────────────────────────
# LLM scoring
# ─────────────────────────────────────────────

async def _llm_score(
    query: str,
    candidates: list[dict],
) -> list[dict]:

    items = []

    for c in candidates:

        cid = str(c.get("chunk_id", ""))

        short_id = cid[:SHORT_ID_LEN]

        title = c.get("title", "")

        text = _clean_text(
            (c.get("content") or "")[:MAX_CHARS]
        )

        items.append(
            f"[{short_id}] {title}\n{text}"
        )

    prompt = (
        f'Câu hỏi: "{query}"\n\n'
        f'Đánh giá {len(items)} đoạn văn sau:\n\n'
        + "\n\n".join(items)
        + "\n\nTrả về scores:"
    )

    id_map = {
        str(c.get("chunk_id", ""))[:SHORT_ID_LEN]:
        str(c.get("chunk_id", ""))
        for c in candidates
    }

    async with httpx.AsyncClient(timeout=30) as client:

        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": RERANK_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {
                    "num_predict": 300,
                    "temperature": 0.0,
                },
            },
        )

        resp.raise_for_status()

        raw = resp.json()["message"]["content"].strip()

    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    m = re.search(r"\{.*\}", raw, re.DOTALL)

    if not m:
        return []

    data = json.loads(m.group(0))

    results = []

    for item in data.get("scores", []):

        short_id = item.get("id", "")[:SHORT_ID_LEN]

        full_id = id_map.get(short_id, short_id)

        try:
            score = int(item.get("score", 1))
        except:
            score = 1

        results.append(
            {
                "id": full_id,
                "score": score,
            }
        )

    return results


# ─────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _make_cache_key(
    query: str,
    candidates: list[dict],
) -> str:

    chunk_ids = ",".join(
        str(c.get("chunk_id", ""))[:SHORT_ID_LEN]
        for c in candidates
    )

    raw = f"{query.lower().strip()}|{chunk_ids}"

    return hashlib.md5(raw.encode()).hexdigest()