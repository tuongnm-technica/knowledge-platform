"""
tasks/grouping.py

Heuristic grouping/clustering for AI task drafts.

Goal (demo + MVP):
- Group by explicit epic_key first (strong signal).
- Then cluster remaining drafts by token overlap (Jaccard) on title/description.

This keeps dependencies at zero while still enabling bulk triage by topic.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter


_STOPWORDS = {
    # EN
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "a",
    "an",
    "is",
    "are",
    "be",
    "as",
    "at",
    "from",
    "by",
    "this",
    "that",
    "it",
    "we",
    "you",
    "i",
    # VI (very small, pragmatic)
    "va",
    "voi",
    "cho",
    "tu",
    "den",
    "trong",
    "tren",
    "nay",
    "do",
    "la",
    "cua",
    "mot",
    "nhieu",
    "can",
    "se",
    "da",
    "dang",
    "khong",
}


def _tokenize(text: str) -> set[str]:
    text = (text or "").lower()
    # \w is unicode-aware in Python; good enough for VI words too.
    toks = re.findall(r"[\w\-]{3,}", text, flags=re.UNICODE)
    out: set[str] = set()
    for t in toks:
        t = t.strip("_-")
        if not t or t.isdigit():
            continue
        if t in _STOPWORDS:
            continue
        out.add(t)
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / max(1, union)


class _DSU:
    def __init__(self, n: int):
        self.p = list(range(n))
        self.r = [0] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.r[ra] < self.r[rb]:
            self.p[ra] = rb
            return
        if self.r[ra] > self.r[rb]:
            self.p[rb] = ra
            return
        self.p[rb] = ra
        self.r[ra] += 1


def group_drafts(
    drafts: list[dict],
    *,
    similarity_threshold: float = 0.30,
    max_items_for_clustering: int = 220,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (drafts_with_group_id, groups).

    groups: [{ id, title, count, draft_ids }]
    """
    if not drafts:
        return drafts, []

    # Make a shallow copy so we don't mutate callers unexpectedly.
    drafts = [dict(d) for d in drafts]

    # 1) Group by epic_key (strong signal).
    groups: dict[str, list[int]] = {}
    group_titles: dict[str, str] = {}
    unassigned: list[int] = []
    for idx, d in enumerate(drafts):
        epic_key = str(d.get("epic_key") or "").strip()
        if epic_key:
            gid = f"epic:{epic_key}"
            groups.setdefault(gid, []).append(idx)
            group_titles[gid] = f"Epic {epic_key}"
            continue
        unassigned.append(idx)

    # 2) Topic clustering on remaining drafts (best-effort).
    if len(unassigned) <= max_items_for_clustering:
        token_sets: list[set[str]] = []
        for idx in unassigned:
            d = drafts[idx]
            text = f"{d.get('title') or ''}\n{d.get('description') or ''}"
            token_sets.append(_tokenize(text))

        dsu = _DSU(len(unassigned))
        for i in range(len(unassigned)):
            for j in range(i + 1, len(unassigned)):
                if _jaccard(token_sets[i], token_sets[j]) >= similarity_threshold:
                    dsu.union(i, j)

        clusters: dict[int, list[int]] = {}
        for local_i, global_idx in enumerate(unassigned):
            root = dsu.find(local_i)
            clusters.setdefault(root, []).append(global_idx)

        for _, members in clusters.items():
            if len(members) < 2:
                continue
            # derive a small "topic title" from top tokens
            c = Counter()
            for gi in members:
                text = f"{drafts[gi].get('title') or ''} {drafts[gi].get('description') or ''}"
                c.update(list(_tokenize(text)))
            top = [t for t, _ in c.most_common(4)]
            label = " ".join(top).strip() or "topic"
            h = hashlib.sha1(label.encode("utf-8")).hexdigest()[:10]
            gid = f"topic:{h}"
            groups[gid] = members
            group_titles[gid] = f"Topic: {label}"
            # Remove from ungrouped: we will assign group_id below anyway.

    # 3) Assign group_id to drafts.
    idx_to_gid: dict[int, str] = {}
    for gid, members in groups.items():
        for idx in members:
            idx_to_gid[idx] = gid

    for idx, d in enumerate(drafts):
        d["group_id"] = idx_to_gid.get(idx, "ungrouped")

    # 4) Build group list for UI.
    out_groups: list[dict] = []
    for gid, members in groups.items():
        title = group_titles.get(gid) or ("Epic " + gid.split(":", 1)[1] if gid.startswith("epic:") else "Related drafts")
        out_groups.append(
            {
                "id": gid,
                "title": title,
                "count": len(members),
                "draft_ids": [str(drafts[i].get("id")) for i in members],
            }
        )

    # Ungrouped bucket (always present if there are any leftovers)
    ungrouped = [str(drafts[i].get("id")) for i in range(len(drafts)) if drafts[i].get("group_id") == "ungrouped"]
    if ungrouped:
        out_groups.append(
            {
                "id": "ungrouped",
                "title": "Ungrouped",
                "count": len(ungrouped),
                "draft_ids": ungrouped,
            }
        )

    out_groups.sort(key=lambda g: int(g.get("count") or 0), reverse=True)
    return drafts, out_groups
