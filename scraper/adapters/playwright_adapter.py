from __future__ import annotations

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scraper.adapters.html import extract_listings
from scraper.models import Listing
from scraper.sources_config import SourceConfig


class PlaywrightAdapter:
    """For the handful of sources that require JS rendering. Reuses the html
    adapter's selector-based extraction once the page has fully loaded."""

    def collect(self, config: SourceConfig) -> list[Listing]:
        if not config.url or config.url == "TBD":
            raise ValueError(f"Source '{config.name}' has no URL configured yet")

        item_selector = config.parser_options.get("item_selector")
        if not item_selector:
            raise ValueError(f"Source '{config.name}' is missing parser_options.item_selector")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(config.url, wait_until="networkidle", timeout=45000)
                html = page.content()
            finally:
                browser.close()

        soup = BeautifulSoup(html, "lxml")
        return extract_listings(soup.select(item_selector), config)
