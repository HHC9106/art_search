from __future__ import annotations

import os

import requests

from scraper.adapters.parsing_utils import parse_deadline
from scraper.models import Listing, make_id
from scraper.sources_config import SourceConfig
from scraper.tier import region_tier

API_URL = "https://www.googleapis.com/customsearch/v1"

# Restricts results to content Google has indexed within roughly the past
# year - the closest legitimate freshness signal the API offers (this is a
# rolling window, not "this calendar year", which is actually more useful:
# a call posted last December is still "fresh" for most of this year).
DATE_RESTRICT = "y1"
RESULTS_PER_QUERY = 10


class GoogleSearchAdapter:
    """Runs a set of themed search queries through Google's Custom Search
    JSON API - not HTML scraping. Direct scraping of Google Search results
    is blocked by CAPTCHA/bot detection and against Google's Terms of
    Service; this API is the sanctioned way to do this programmatically."""

    def collect(self, config: SourceConfig) -> list[Listing]:
        api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
        engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
        if not api_key or not engine_id:
            raise ValueError(
                "GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID must be set "
                "(environment variables / GitHub secrets) to use adapter: google_search"
            )

        queries = config.parser_options.get("search_queries") or []
        if not queries:
            raise ValueError(f"Source '{config.name}' has no parser_options.search_queries configured")

        listings: list[Listing] = []
        for query in queries:
            try:
                response = requests.get(
                    API_URL,
                    params={
                        "key": api_key,
                        "cx": engine_id,
                        "q": query,
                        "dateRestrict": DATE_RESTRICT,
                        "num": RESULTS_PER_QUERY,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:  # noqa: BLE001 - one bad query must never drop the other nine
                print(f"::warning::google_search query failed ({query!r}): {exc}")
                continue
            listings.extend(_listings_from_response(data, config, query))
        return listings


def _listings_from_response(data: dict, config: SourceConfig, query: str) -> list[Listing]:
    listings = []
    for item in data.get("items") or []:
        title = (item.get("title") or "").strip()
        url = (item.get("link") or "").strip()
        if not title or not url:
            continue

        snippet = item.get("snippet") or None
        deadline, deadline_raw = parse_deadline(snippet)
        organizer = item.get("displayLink") or config.organizer or config.display_name

        listings.append(
            Listing(
                id=make_id(config.name, url),
                title=title,
                organizer=organizer,
                source_name=config.name,
                url=url,
                country=config.country,
                region_tier=region_tier(config.country, config.region_tier_override),
                listing_type=config.listing_type,
                deadline=deadline,
                deadline_raw=deadline_raw,
                description=snippet,
                raw_extra={"search_query": query},
            )
        )
    return listings
