from __future__ import annotations

from typing import Protocol

from scraper.models import Listing
from scraper.sources_config import SourceConfig


class SourceAdapter(Protocol):
    def collect(self, config: SourceConfig) -> list[Listing]: ...


def get_adapter(adapter_type: str) -> SourceAdapter:
    if adapter_type == "rss":
        from scraper.adapters.rss import RssAdapter
        return RssAdapter()
    if adapter_type == "html":
        from scraper.adapters.html import HtmlAdapter
        return HtmlAdapter()
    if adapter_type == "manual":
        from scraper.adapters.manual import ManualAdapter
        return ManualAdapter()
    if adapter_type == "playwright":
        from scraper.adapters.playwright_adapter import PlaywrightAdapter
        return PlaywrightAdapter()
    if adapter_type == "custom":
        from scraper.adapters.custom import CustomAdapter
        return CustomAdapter()
    raise ValueError(f"Unknown adapter type: {adapter_type!r}")
