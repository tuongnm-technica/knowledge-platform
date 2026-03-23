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
import asyncio
import json
import re
import time
import httpx
import structlog
from services.llm_service import LLMService

from config.settings import settings
from prompts.retrieval_prompt import RERANK_SYSTEM

log = structlog.get_logger()


# ─────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────

_rerank_cache: dict[str, tuple[list[dict], float]] = {}

_CACHE_TTL = 120

SHORT_ID_LEN = 12
MAX_CHARS = 1500
MAX_RERANK = 15

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:

    global _http_client

    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=120)

    return _http_client


_cross_encoder = None
_cross_encoder_lock: asyncio.Lock | None = None


def _backend_name() -> str:
    try:
        return str(getattr(settings, "RERANKER_BACKEND", "llm") or "llm").strip().lower()
    except Exception:
        return "llm"


def _should_skip_rerank(candidates: list[dict]) -> bool:
    # Heuristic: skip rerank if score already very confident.
    try:
        best_score = float(candidates[0].get("rrf_score", 0) or 0)
    except Exception:
        best_score = 0.0
    return best_score > 0.9


# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────


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

    llm = LLMService()
    if len(candidates) <= top_k:
        return candidates

    if not getattr(settings, "RERANKING_ENABLED", True):
        return candidates[:top_k]

    backend = _backend_name()

    if backend in ("none", "off", "disabled", "false", "0"):
        return candidates[:top_k]

    if _should_skip_rerank(candidates):
        log.debug("reranker.skip_high_confidence", backend=backend)
        return candidates[:top_k]

    if backend == "cross_encoder":
        try:
            return await _rerank_cross_encoder(query, candidates, top_k=top_k)
        except Exception as e:
            log.warning("reranker.cross_encoder.failed", error=str(e))
            # Fallback to LLM reranker (best-effort).
            return await _rerank_llm(query, candidates, top_k=top_k)

    # default / "llm"
    return await _rerank_llm(query, candidates, top_k=top_k)


async def _rerank_llm(
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

    cache_key = _make_cache_key("llm", settings.OLLAMA_LLM_MODEL, query, candidates[:MAX_RERANK])

    if cache_key in _rerank_cache:

        results, ts = _rerank_cache[cache_key]

        if time.time() - ts < _CACHE_TTL:
            log.debug("reranker.cache_hit", backend="llm", query=query[:60])
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

            original = float(c.get("final_score") or c.get("rrf_score") or 0.0)

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
            backend="llm",
            query=query[:60],
            candidates=len(to_rerank),
            top_k=top_k
        )

        return result

    except Exception as e:

        log.warning("reranker.failed", error=str(e))

        return candidates[:top_k]


# ─────────────────────────────────────────────
# Cross-encoder reranker
async def _get_cross_encoder():

    global _cross_encoder, _cross_encoder_lock

    if _cross_encoder is not None:
        return _cross_encoder

    if _cross_encoder_lock is None:
        _cross_encoder_lock = asyncio.Lock()

    async with _cross_encoder_lock:

        if _cross_encoder is not None:
            return _cross_encoder

        model_id = str(getattr(settings, "CROSS_ENCODER_MODEL", "") or "").strip()

        if not model_id:
            raise ValueError("CROSS_ENCODER_MODEL is empty")

        device = str(getattr(settings, "CROSS_ENCODER_DEVICE", "cpu") or "cpu").strip()

        from sentence_transformers import CrossEncoder

        log.info("reranker.cross_encoder.load", model=model_id, device=device)
        _cross_encoder = CrossEncoder(model_id, device=device)

        return _cross_encoder


async def _rerank_cross_encoder(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:

    if not candidates:
        return []

    if len(candidates) <= top_k:
        return candidates

    cache_key = _make_cache_key(
        "cross_encoder",
        getattr(settings, "CROSS_ENCODER_MODEL", ""),
        query,
        candidates[:MAX_RERANK],
    )

    if cache_key in _rerank_cache:

        results, ts = _rerank_cache[cache_key]

        if time.time() - ts < _CACHE_TTL:
            log.debug("reranker.cache_hit", backend="cross_encoder", query=query[:60])
            return results

    to_rerank = candidates[:MAX_RERANK]
    rest = candidates[MAX_RERANK:]

    model = await _get_cross_encoder()

    pairs = []

    for c in to_rerank:
        text = _clean_text((c.get("content") or "")[:MAX_CHARS])
        pairs.append((str(query or ""), text))

    scores = await asyncio.to_thread(
        model.predict,
        pairs,
        show_progress_bar=False,
    )

    try:
        scores_list = [float(s) for s in list(scores)]
    except Exception:
        scores_list = [float(s) for s in scores]

    orig_scores = [
        c.get("final_score", c.get("rrf_score", 0))
        for c in to_rerank
    ]
    max_orig = max(orig_scores) or 1

    for c, ce_score in zip(to_rerank, scores_list):
        original = float(c.get("final_score") or c.get("rrf_score") or 0.0)
        norm_orig = (original / max_orig) if max_orig else 0.0
        c["cross_encoder_relevance"] = float(ce_score or 0.0)
        c["rerank_score"] = float(ce_score or 0.0) + (0.01 * float(norm_orig))

    reranked = sorted(
        to_rerank,
        key=lambda x: x.get("rerank_score", 0),
        reverse=True,
    )

    result = (reranked + rest)[:top_k]
    _rerank_cache[cache_key] = (result, time.time())

    log.info(
        "reranker.done",
        backend="cross_encoder",
        query=query[:60],
        candidates=len(to_rerank),
        top_k=top_k,
    )

    return result


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

    llm_client = LLMService()
    raw = await llm_client.chat(
        system=RERANK_SYSTEM,
        user=prompt,
        max_tokens=300
    )

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
    backend: str,
    model_id: str,
    query: str,
    candidates: list[dict],
) -> str:

    chunk_ids = ",".join(
        str(c.get("chunk_id", ""))[:SHORT_ID_LEN]
        for c in candidates
    )

    raw = (
        f"{str(backend or '').strip().lower()}|"
        f"{str(model_id or '').strip()}|"
        f"{query.lower().strip()}|"
        f"{chunk_ids}"
    )

    return hashlib.md5(raw.encode()).hexdigest()
