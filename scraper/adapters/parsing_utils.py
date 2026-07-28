from __future__ import annotations

import re
from datetime import date, datetime

USER_AGENT = "art-search-bot/1.0 (+mailto:andyentre@gmail.com; personal open-call aggregator)"

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}")
_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y")


def select_text(item, selector: str | None) -> str | None:
    if not selector:
        return None
    el = item.select_one(selector)
    return el.get_text(strip=True) if el else None


def parse_deadline(text: str | None) -> tuple[date | None, str | None]:
    """Best-effort deadline extraction from free-form scraped text.

    Deliberately permissive: falls back to keeping the raw text (deadline=None,
    deadline_raw=text) whenever the date can't be confidently parsed, so nothing
    is silently dropped — a human can review deadline_raw later.
    """
    if not text:
        return None, None
    match = _DATE_PATTERN.search(text)
    if not match:
        return None, text
    raw = match.group(0)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date(), text
        except ValueError:
            continue
    return None, text
