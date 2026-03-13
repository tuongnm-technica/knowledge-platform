"""
retrieval/query_expansion.py
─────────────────────────────
Mở rộng query trước khi search để tăng recall.

Chiến lược:
1. LLM-based expansion: sinh ra 2-3 query variants bằng tiếng Việt
2. Kết quả search từ tất cả variants → merge bằng RRF
3. Cache expansion result (TTL 5 phút) để tránh gọi LLM lặp lại

Ví dụ:
  Input:  "API lấy thông tin xe ECOR"
  Output: [
    "API lấy thông tin xe ECOR",              # original
    "endpoint truy vấn dữ liệu xe ECOR",      # variant 1
    "REST API xe ECOR thông tin phương tiện",  # variant 2
  ]
"""
from __future__ import annotations
import hashlib
import time
import json
import re
import httpx
import structlog
from config.settings import settings

log = structlog.get_logger()

# ─── In-memory cache ──────────────────────────────────────────────────────────
_cache: dict[str, tuple[list[str], float]] = {}   # key → (variants, timestamp)
_CACHE_TTL = 300  # 5 phút


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


# ─── LLM Expansion ────────────────────────────────────────────────────────────

EXPANSION_SYSTEM = """\
Bạn là expert search query optimizer cho hệ thống tài liệu kỹ thuật nội bộ (Confluence, Jira, Slack).

Nhiệm vụ: Sinh ra 2 query variants để tìm kiếm tài liệu liên quan tốt hơn.

Quy tắc:
- Giữ nguyên ý nghĩa gốc, KHÔNG thêm thông tin mới
- Dùng từ đồng nghĩa, cách diễn đạt khác
- Mix tiếng Việt và tiếng Anh kỹ thuật tự nhiên
- Mỗi variant ngắn gọn (< 15 từ)

⚠️ Trả về JSON THUẦN TÚY:
{"variants": ["variant 1", "variant 2"]}
"""


async def expand_query(query: str, use_llm: bool = True) -> list[str]:
    """
    Trả về [original_query, variant1, variant2].
    Fallback về [original_query] nếu LLM fail.
    """
    # Check cache trước
    cached = _get_cached(query)
    if cached:
        log.debug("query_expansion.cache_hit", query=query[:50])
        return cached

    variants = [query]  # luôn giữ original

    if not use_llm:
        return variants

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model":   settings.OLLAMA_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": EXPANSION_SYSTEM},
                        {"role": "user",   "content": f'Query: "{query}"'},
                    ],
                    "stream":  False,
                    "options": {"num_predict": 150, "temperature": 0.3},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()

        # Parse JSON
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            for v in data.get("variants", []):
                v = v.strip()
                if v and v.lower() != query.lower() and len(v) > 3:
                    variants.append(v)

        log.info("query_expansion.done", original=query[:50], variants=len(variants))

    except Exception as e:
        log.warning("query_expansion.failed", error=str(e))
        # Fallback: rule-based expansion (không cần LLM)
        variants.extend(_rule_based_expand(query))

    # Deduplicate
    seen = set()
    unique = []
    for v in variants:
        k = v.lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(v)

    result = unique[:3]  # max 3 queries (original + 2 variants)
    _set_cache(query, result)
    return result


def _rule_based_expand(query: str) -> list[str]:
    """Fallback expansion không cần LLM — dùng synonym dict đơn giản."""
    synonyms = {
        "api":        ["endpoint", "REST API", "interface"],
        "lỗi":        ["bug", "error", "issue", "sự cố"],
        "deploy":     ["triển khai", "release", "deployment"],
        "tài liệu":   ["document", "docs", "spec", "specification"],
        "hướng dẫn":  ["guide", "tutorial", "cách làm", "how to"],
        "cấu hình":   ["config", "configuration", "setup", "cài đặt"],
        "database":   ["db", "cơ sở dữ liệu", "PostgreSQL", "SQL"],
        "người dùng": ["user", "account", "tài khoản"],
    }
    q_lower = query.lower()
    variants = []
    for word, syns in synonyms.items():
        if word in q_lower:
            # Tạo 1 variant với synonym đầu tiên
            v = query.replace(word, syns[0])
            if v != query:
                variants.append(v)
                break
    return variants[:1]