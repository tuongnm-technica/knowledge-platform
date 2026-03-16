from __future__ import annotations
import hashlib
import time
import json
import re
import httpx
import structlog
from config.settings import settings
from utils.ollama_api import ollama_chat

log = structlog.get_logger()

MAX_EXPANSIONS = 2

_http_client: httpx.AsyncClient | None = None

_cache: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 300


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15)
    return _http_client


def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def _get_cached(query: str) -> list[str] | None:

    key = _cache_key(query)

    if key in _cache:
        variants, ts = _cache[key]

        if time.time() - ts < _CACHE_TTL:
            return variants

        del _cache[key]

    return None


def _set_cache(query: str, variants: list[str]) -> None:
    _cache[_cache_key(query)] = (variants, time.time())


EXPANSION_SYSTEM = """
Bạn là expert search query optimizer cho hệ thống tài liệu kỹ thuật nội bộ.

Giữ nguyên query gốc. 
Và Sinh ra 2 query variants.
=> tổng có 3 query (1 original + 2 variants).

Rules:
- giữ nguyên meaning
- dùng synonyms
- mix EN / VN
- < 15 words

Return JSON:

{"variants":["variant1","variant2"]}
"""


async def expand_query(query: str, use_llm: bool = True) -> list[str]:

    variants = [query]

    cached = _get_cached(query)

    if cached:
        log.debug("query_expansion.cache_hit", query=query[:50])
        return cached

    if not use_llm:
        return variants

    try:

        client = _get_http_client()

        raw = await ollama_chat(
            model=settings.OLLAMA_LLM_MODEL,
            messages=[
                {"role": "system", "content": EXPANSION_SYSTEM},
                {"role": "user", "content": f'Query: "{query}"'},
            ],
            options={"num_predict": 120, "temperature": 0.3},
            timeout=15,
            client=client,
        )

        raw = re.sub(r"```(?:json)?|```", "", raw).strip()

        m = re.search(r"\{.*\}", raw, re.DOTALL)

        if m:

            data = json.loads(m.group(0))

            for v in data.get("variants", []):

                v = v.strip()

                if v and v.lower() != query.lower():

                    variants.append(v)

    except Exception as e:

        log.warning("query_expansion.failed", error=str(e))

    seen = set()
    unique = []

    for v in variants:

        k = v.lower().strip()

        if k not in seen:
            seen.add(k)
            unique.append(v)

    result = unique[: 1 + MAX_EXPANSIONS]

    _set_cache(query, result)

    log.info(
        "query_expansion.done",
        original=query[:50],
        variants=len(result) - 1,
    )

    return result
