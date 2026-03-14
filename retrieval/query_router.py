import re
from collections import Counter


def route_query_advanced(query: str) -> str:

    q = query.lower().strip()

    weights = {
        "slack": {
            "keywords": [r"chat", r"conversation", r"message", r"huddle", r"thảo luận"],
            "weight": 1
        },
        "jira": {
            "keywords": [r"bug", r"issue", r"ticket", r"task", r"fix", r"lỗi"],
            "weight": 1.5
        },
        "confluence": {
            "keywords": [r"api", r"design", r"spec", r"architecture", r"documentation", r"tài liệu"],
            "weight": 1.2
        },
        "file_server": {
            "keywords": [r"report", r"excel", r"xlsx", r"pdf", r"slide", r"powerpoint"],
            "weight": 1
        }
    }

    scores = Counter()

    for source, data in weights.items():

        for pattern in data["keywords"]:

            if re.search(rf"\b{pattern}\b", q):
                scores[source] += data["weight"]

    # ambiguous keyword
    if re.search(r"\bmeeting\b", q):
        scores["slack"] += 1
        scores["confluence"] += 0.8

    if not scores:
        return "all"

    return scores.most_common(1)[0][0]