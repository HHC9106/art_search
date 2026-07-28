from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceConfig:
    name: str
    adapter: str
    enabled: bool = True
    display_name: str = ""
    organizer: str = ""
    country: str | None = None
    region_tier_override: str | None = None  # top | high | medium | low
    url: str | None = None
    listing_type: str = "open_call"
    parser_options: dict[str, Any] = field(default_factory=dict)
    manual_entries: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    frequency: str = "weekly"  # weekly | quarterly - how often this source should be checked
    apply_relevance_filter: bool = False  # strong allow-list filter, for multi-source aggregators


def load_sources(path: str | Path) -> list[SourceConfig]:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []

    sources: list[SourceConfig] = []
    seen_names: set[str] = set()
    for entry in raw:
        name = entry["name"]
        if name in seen_names:
            raise ValueError(f"Duplicate source name in {path.name}: {name}")
        seen_names.add(name)
        sources.append(
            SourceConfig(
                name=name,
                adapter=entry["adapter"],
                enabled=entry.get("enabled", True),
                display_name=entry.get("display_name", name),
                organizer=entry.get("organizer", ""),
                country=entry.get("country"),
                region_tier_override=entry.get("region_tier"),
                url=entry.get("url"),
                listing_type=entry.get("listing_type", "open_call"),
                parser_options=entry.get("parser_options") or {},
                manual_entries=entry.get("manual_entries") or [],
                notes=entry.get("notes", ""),
                frequency=entry.get("frequency", "weekly"),
                apply_relevance_filter=entry.get("apply_relevance_filter", False),
            )
        )
    return sources


def enabled_sources(path: str | Path) -> list[SourceConfig]:
    return [s for s in load_sources(path) if s.enabled]
