from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

TIER_LEVELS = ("top", "high", "medium", "low")

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "tier_config.yaml"


@lru_cache(maxsize=None)
def _load_config(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    levels = raw.get("levels") or {}
    lookup: dict[str, str] = {}
    for tier in TIER_LEVELS:
        for country in levels.get(tier) or []:
            lookup[country.strip().lower()] = tier
    default = raw.get("default", "low")
    if default not in TIER_LEVELS:
        raise ValueError(f"tier_config.yaml default {default!r} must be one of {TIER_LEVELS}")
    return {"lookup": lookup, "default": default}


def region_tier(country: str | None, override: str | None = None, config_path: Path | None = None) -> str:
    """Nation/region -> priority tier (top/high/medium/low), driven by
    tier_config.yaml so the mapping is user-editable without code changes.
    The dashboard additionally lets tiers be overridden live in the browser -
    this is just the server-side default used at scrape time and for the
    email digest.
    """
    if override is not None:
        return override
    config = _load_config(config_path or DEFAULT_CONFIG_PATH)
    normalized = (country or "").strip().lower()
    return config["lookup"].get(normalized, config["default"])
