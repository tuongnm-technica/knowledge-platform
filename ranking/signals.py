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
    if updated_at is None or not hasattr(updated_at, "days"):
        # Check if it's a string that looks like a date (best effort)
        if isinstance(updated_at, str) and len(updated_at) > 10:
             try:
                 from dateutil.parser import parse
                 updated_at = parse(updated_at)
             except Exception:
                 return 0.0
        else:
            return 0.0

    now = datetime.now(timezone.utc)
    if hasattr(updated_at, "tzinfo") and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    
    days = 0
    try:
        delta = now - updated_at
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
