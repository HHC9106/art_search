from __future__ import annotations

# Personal practice focus. Extend freely — this is just a keyword→tag lookup,
# not a controlled taxonomy, so new tags/keywords are a config-only change.
DISCIPLINE_TAGS: dict[str, dict[str, object]] = {
    "new_media_art": {
        "label": "New Media Art",
        "keywords": ["new media art", "new media"],
    },
    "digital_art": {
        "label": "Digital Art",
        "keywords": ["digital art", "digital media art"],
    },
    "data_art": {
        "label": "Data Art",
        "keywords": ["data art", "data visualization art", "data-driven art", "data-driven"],
    },
    "civic_tech": {
        "label": "Civic Tech",
        "keywords": ["civic tech", "civic technology"],
    },
    "open_data": {
        "label": "Open Data",
        "keywords": ["open data"],
    },
    "urban_data": {
        "label": "Urban Data",
        "keywords": ["urban data", "urban informatics", "smart city", "smart cities", "urban"],
    },
    "information_art": {
        "label": "Information Art",
        "keywords": ["information art", "information design art", "infographic art"],
    },
}


def auto_tag_discipline(text: str | None) -> list[str]:
    """Best-effort keyword match over free text (title/description/eligibility)
    against the personal-practice tag set above. Returns matched tag keys,
    sorted for stable output; empty if nothing matches."""
    if not text:
        return []
    haystack = text.lower()
    matched = [
        tag
        for tag, spec in DISCIPLINE_TAGS.items()
        if any(keyword in haystack for keyword in spec["keywords"])
    ]
    return sorted(matched)


def tag_label(tag: str) -> str:
    spec = DISCIPLINE_TAGS.get(tag)
    return spec["label"] if spec else tag
