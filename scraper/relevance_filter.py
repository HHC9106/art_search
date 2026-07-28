from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "exclude_keywords.yaml"


@lru_cache(maxsize=None)
def _load_keywords(path: Path) -> tuple[str, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return tuple(kw.strip().lower() for kw in (raw.get("keywords") or []) if kw.strip())


def is_excluded(text: str | None, config_path: Path | None = None) -> bool:
    """True if text matches any exclude_keywords.yaml entry (case-insensitive
    substring match) - used to drop listings whose subject/medium/type doesn't
    match your practice, regardless of which source scraped them."""
    if not text:
        return False
    haystack = text.lower()
    return any(keyword in haystack for keyword in _load_keywords(config_path or DEFAULT_CONFIG_PATH))
