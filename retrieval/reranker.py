"""
retrieval/reranker.py
──────────────────────
LLM-based reranker cho kết quả search.

Flow:
    Hybrid search → top candidates
    → Reranker (LLM đánh giá relevance)
    → top_k kết quả tốt nhất

Optimization:
    - Skip rerank nếu confidence cao
    - Chỉ rerank top 10
    - Batch scoring (1 LLM call)
    - Cache theo (model + query + chunk_ids)
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
MAX_CHARS = 1500
MAX_RERANK = 3

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:

    global _http_client

    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=120)

    return _http_client


# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────

RERANK_SYSTEM = """
Bạn là chuyên gia phân tích dữ liệu dự án.
Nhiệm vụ: Chấm điểm (0-3) mức độ liên quan giữa câu hỏi và đoạn văn.

QUY TẮC BẮT BUỘC:
1. Nếu câu hỏi có mốc thời gian (vd: 9/2), nội dung PHẢI nhắc đến sự kiện hoặc yêu cầu của ngày đó mới được điểm 3, kể cả khi ngày tạo văn bản là ngày khác.
2. Tuyệt đối Ưu tiên nội dung từ content hơn title. Sau đó mới xem xét title.
3. Ưu tiên cao các từ khóa chuyên môn như "Auction", "đấu giá", "kế hoạch 2026".

Thang điểm:
3: Trả lời trực tiếp nội dung sự kiện/yêu cầu của ngày được hỏi.
2: Có liên quan mật thiết nhưng không nhắc trực tiếp ngày.
1: Chỉ liên quan gián tiếp hoặc chung chung.
0: Không liên quan.
"""


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

async def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:

    if not candidates:
        return []

    if len(candidates) <= top_k:
        return candidates

    # ─────────────────────────────
    # Skip rerank nếu score cao
    # ─────────────────────────────

    best_score = candidates[0].get("rrf_score", 0)

    if best_score > 0.9:
        log.debug("reranker.skip_high_confidence")
        return candidates[:top_k]

    # ─────────────────────────────
    # Cache key
    # ─────────────────────────────

    cache_key = _make_cache_key(query, candidates[:MAX_RERANK])

    if cache_key in _rerank_cache:

        results, ts = _rerank_cache[cache_key]

        if time.time() - ts < _CACHE_TTL:
            log.debug("reranker.cache_hit", query=query[:60])
            return results

    to_rerank = candidates[:MAX_RERANK]
    rest = candidates[MAX_RERANK:]

    try:

        scores = await _llm_score(query, to_rerank)

        score_map = {
            s["id"][:SHORT_ID_LEN]: s["score"]
            for s in scores
        }

        orig_scores = [
            c.get("final_score", c.get("rrf_score", 0))
            for c in to_rerank
        ]

        max_orig = max(orig_scores) or 1

        for c in to_rerank:

            cid = str(c.get("chunk_id", ""))[:SHORT_ID_LEN]

            llm_score = score_map.get(cid, 1)

            # clamp score
            llm_score = max(0, min(llm_score, 3))

            original = c.get("final_score", c.get("rrf_score", 0))

            norm_orig = original / max_orig

            c["llm_relevance"] = llm_score

            # c["rerank_score"] = round( 0.6 * (llm_score / 3.0)  + 0.4 * norm_orig,  4 )
            c["rerank_score"] = llm_score  +(0.1 * norm_orig)

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

    client = _get_http_client()

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

    try:
        data = json.loads(m.group(0))
    except Exception:
        return []

    results = []

    for item in data.get("scores", []):

        short_id = item.get("id", "")[:SHORT_ID_LEN]

        full_id = id_map.get(short_id, short_id)

        try:
            score = int(item.get("score", 1))
        except Exception:
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
    return re.sub(r"\s+", " ", text).strip()


def _make_cache_key(
    query: str,
    candidates: list[dict],
) -> str:

    chunk_ids = ",".join(
        str(c.get("chunk_id", ""))[:SHORT_ID_LEN]
        for c in candidates
    )

    raw = (
        f"{settings.OLLAMA_LLM_MODEL}|"
        f"{query.lower().strip()}|"
        f"{chunk_ids}"
    )

    return hashlib.md5(raw.encode()).hexdigest()