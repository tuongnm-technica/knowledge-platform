from datetime import datetime, timezone
import math
from typing import Any


def semantic_signal(score: Any) -> float:
    try:
        val = float(score or 0.0)
        return max(0.0, min(1.0, val))
    except (ValueError, TypeError):
        return 0.0


def keyword_signal(score: Any) -> float:
    try:
        val = float(score or 0.0)
        if val <= 0:
            return 0.0
        return min(val / 5.0, 1.0)
    except (ValueError, TypeError):
        return 0.0


def graph_signal(score: Any) -> float:
    try:
        val = float(score or 0.0)
        return max(0.0, min(1.0, val))
    except (ValueError, TypeError):
        return 0.0


def recency_signal(updated_at: Any) -> float:
    if updated_at is None:
        return 0.0

    # Ensure we have a datetime object
    dt = updated_at
    if isinstance(dt, str) and len(dt) > 10:
        try:
            from dateutil.parser import parse
            dt = parse(dt)
        except Exception:
            return 0.0
    
    if not hasattr(dt, "tzinfo"):
        return 0.0

    now = datetime.now(timezone.utc)
    # Convert dt to UTC if it's naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    try:
        delta = now - dt
        days = delta.days
    except (ValueError, TypeError):
        return 0.0
    if days <= 7:   return 1.0
    if days <= 30:  return 0.7
    if days <= 90:  return 0.4
    if days <= 365: return 0.2
    return 0.05


def popularity_signal(click_count: int = 0) -> float:
    return min(1.0, math.log1p(click_count) / math.log1p(1000))
