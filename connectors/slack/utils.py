from __future__ import annotations


def slack_deep_link(channel_id: str, ts: str) -> str:
    """Tạo deep link tới một message trên Slack."""
    ts = str(ts or "").strip()
    if not ts:
        return f"https://slack.com/archives/{channel_id}"
    if "." in ts:
        sec, frac = ts.split(".", 1)
        frac = (frac + "000000")[:6]
        ts_digits = f"{sec}{frac}"
    else:
        ts_digits = "".join([c for c in ts if c.isdigit()])
    return f"https://slack.com/archives/{channel_id}/p{ts_digits}"