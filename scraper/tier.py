from __future__ import annotations

TIER_1_COUNTRIES = {
    "uk", "united kingdom", "england", "scotland", "wales",
    "northern ireland", "gb", "great britain",
}

EU_COUNTRY_NAMES = {
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic", "czechia",
    "denmark", "estonia", "finland", "france", "germany", "greece", "hungary",
    "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta", "netherlands",
    "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
}

TIER_2_COUNTRIES = {
    "us", "usa", "united states", "united states of america", "taiwan", "tw", "roc",
} | EU_COUNTRY_NAMES


def region_tier(country: str | None, override: int | None = None) -> int:
    if override is not None:
        return override
    normalized = (country or "").strip().lower()
    if normalized in TIER_1_COUNTRIES:
        return 1
    if normalized in TIER_2_COUNTRIES:
        return 2
    return 3
