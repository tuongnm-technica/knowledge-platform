"""
utils/embedding_cache.py
─────────────────────────
Cache embedding vectors để tránh gọi Ollama lặp lại cho cùng 1 text.

Tác động:
  - Query embedding: ~500ms → ~0ms (cache hit)
  - Với 100 queries/ngày, ~30% là câu hỏi lặp → tiết kiệm ~15s/ngày
  - Quan trọng hơn: giảm load Ollama trong giờ cao điểm

Design:
  - LRU cache in-memory, max 500 entries
  - Key = md5(text.lower().strip())
  - TTL = 1 giờ (embedding ổn định, không cần expire sớm)
  - Thread-safe với asyncio.Lock

Sử dụng: thay thế trực tiếp get_embedding() trong utils/embeddings.py
"""
from __future__ import annotations
import asyncio
import hashlib
import time
from collections import OrderedDict
import structlog

log = structlog.get_logger()

_MAX_SIZE = 500
_TTL      = 3600  # 1 giờ

# LRU cache: key → (vector, timestamp)
_cache: OrderedDict[str, tuple[list[float], float]] = OrderedDict()
_lock  = asyncio.Lock()

# Stats
_stats = {"hits": 0, "misses": 0}


def _key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


async def get_embedding_cached(text: str) -> list[float] | None:
    """Lấy embedding từ cache. Trả về None nếu miss."""
    k = _key(text)
    async with _lock:
        if k in _cache:
            vec, ts = _cache[k]
            if time.time() - ts < _TTL:
                # LRU: move to end
                _cache.move_to_end(k)
                _stats["hits"] += 1
                log.debug("embedding_cache.hit", key=k[:8])
                return vec
            else:
                del _cache[k]
        _stats["misses"] += 1
        return None


async def set_embedding_cached(text: str, vector: list[float]) -> None:
    """Lưu embedding vào cache."""
    k = _key(text)
    async with _lock:
        if k in _cache:
            _cache.move_to_end(k)
        _cache[k] = (vector, time.time())
        # Evict oldest nếu quá size
        while len(_cache) > _MAX_SIZE:
            _cache.popitem(last=False)


def get_cache_stats() -> dict:
    total = _stats["hits"] + _stats["misses"]
    hit_rate = round(_stats["hits"] / total * 100, 1) if total > 0 else 0
    return {
        "size":     len(_cache),
        "max_size": _MAX_SIZE,
        "hits":     _stats["hits"],
        "misses":   _stats["misses"],
        "hit_rate": f"{hit_rate}%",
    }


def clear_cache() -> None:
    _cache.clear()
    _stats["hits"] = _stats["misses"] = 0