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


STRONG_WEIGHT = 3
WEAK_WEIGHT = 1
DEFAULT_THRESHOLD = 3


@lru_cache(maxsize=None)
def _load_allowlist(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    discipline_keywords = [kw for spec in DISCIPLINE_TAGS.values() for kw in spec["keywords"]]
    strong_keywords = discipline_keywords + [
        kw.strip().lower() for kw in (raw.get("strong_keywords") or []) if kw.strip()
    ]
    weak_keywords = [kw.strip().lower() for kw in (raw.get("weak_keywords") or []) if kw.strip()]
    format_keywords = [kw.strip().lower() for kw in (raw.get("format_keywords") or []) if kw.strip()]
    organizers = [o.strip().lower() for o in (raw.get("organizers") or []) if o.strip()]
    return {
        "strong": tuple(strong_keywords),
        "weak": tuple(weak_keywords + format_keywords),
        "organizers": tuple(organizers),
        "threshold": raw.get("threshold", DEFAULT_THRESHOLD),
    }


def relevance_score(text: str | None, config_path: Path | None = None) -> int:
    """Weighted keyword score for a listing's text: each distinct strong_keywords
    match (discipline_tags.py's vocabulary plus relevance_allowlist.yaml's
    strong_keywords) counts for STRONG_WEIGHT; each distinct weak_keywords/
    format_keywords match counts for WEAK_WEIGHT. Weak/format words describe a
    generic topic or opportunity type (urban, research, commission, grant...)
    that's too common to trust alone, so they only add up in combination -
    strong words are specific enough that one match should already clear the
    default threshold on its own."""
    config = _load_allowlist(config_path or DEFAULT_ALLOWLIST_PATH)
    haystack = (text or "").lower()
    score = STRONG_WEIGHT * sum(1 for kw in config["strong"] if kw in haystack)
    score += WEAK_WEIGHT * sum(1 for kw in config["weak"] if kw in haystack)
    return score


def passes_strong_filter(text: str | None, organizer: str | None, config_path: Path | None = None) -> bool:
    """True if a listing should survive the weighted allow-list filter used for
    multi-source aggregators: its relevance_score() reaches the configured
    threshold, or its organizer is on the allowlist (substring match, e.g. an
    aggregator-listed "V&A South Kensington" matches an allowlisted "Victoria
    and Albert Museum" only if written the same way - kept intentionally
    simple)."""
    config = _load_allowlist(config_path or DEFAULT_ALLOWLIST_PATH)
    if relevance_score(text, config_path) >= config["threshold"]:
        return True
    normalized_organizer = (organizer or "").strip().lower()
    if not normalized_organizer:
        return False
    return any(allowed in normalized_organizer for allowed in config["organizers"])
