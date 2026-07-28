from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from scraper.discipline_tags import DISCIPLINE_TAGS

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "exclude_keywords.yaml"
DEFAULT_ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "relevance_allowlist.yaml"


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


@lru_cache(maxsize=None)
def _load_allowlist(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    discipline_keywords = [kw for spec in DISCIPLINE_TAGS.values() for kw in spec["keywords"]]
    extra_keywords = [kw.strip().lower() for kw in (raw.get("extra_keywords") or []) if kw.strip()]
    organizers = [o.strip().lower() for o in (raw.get("organizers") or []) if o.strip()]
    return {"keywords": tuple(discipline_keywords + extra_keywords), "organizers": tuple(organizers)}


def passes_strong_filter(text: str | None, organizer: str | None, config_path: Path | None = None) -> bool:
    """True if a listing should survive the strong allow-list filter used for
    multi-source aggregators: matches a keyword (discipline_tags.py's
    vocabulary plus relevance_allowlist.yaml's extras), or its organizer is
    on the allowlist (substring match, e.g. an aggregator-listed "V&A South
    Kensington" matches an allowlisted "Victoria and Albert Museum" only if
    written the same way - kept intentionally simple)."""
    config = _load_allowlist(config_path or DEFAULT_ALLOWLIST_PATH)
    haystack = (text or "").lower()
    if any(keyword in haystack for keyword in config["keywords"]):
        return True
    normalized_organizer = (organizer or "").strip().lower()
    if not normalized_organizer:
        return False
    return any(allowed in normalized_organizer for allowed in config["organizers"])
