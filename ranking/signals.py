from datetime import datetime, timezone
import math


def semantic_signal(score: float) -> float:
    return max(0.0, min(1.0, score))


def keyword_signal(score: float) -> float:
    if score <= 0:
        return 0
    return min(score / 5, 1.0)


def recency_signal(updated_at: datetime | None) -> float:
    if updated_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = (now - updated_at).days
    if days <= 7:   return 1.0
    if days <= 30:  return 0.7
    if days <= 90:  return 0.4
    if days <= 365: return 0.2
    return 0.05


def popularity_signal(click_count: int = 0) -> float:
    return min(1.0, math.log1p(click_count) / math.log1p(1000))