from __future__ import annotations

from .scanners.slack import SlackScanner
from .scanners.confluence import ConfluenceScanner

SCANNERS = {
    "slack": SlackScanner,
    "confluence": ConfluenceScanner,
}