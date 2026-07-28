from __future__ import annotations

import feedparser

from scraper.adapters.parsing_utils import parse_deadline
from scraper.models import Listing, make_id
from scraper.sources_config import SourceConfig
from scraper.tier import region_tier


class RssAdapter:
    def collect(self, config: SourceConfig) -> list[Listing]:
        if not config.url or config.url == "TBD":
            raise ValueError(f"Source '{config.name}' has no URL configured yet")

        feed = feedparser.parse(config.url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"Failed to parse RSS feed: {feed.bozo_exception}")

        listings = []
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            summary = entry.get("summary", "") or ""
            deadline, deadline_raw = parse_deadline(summary)

            listings.append(
                Listing(
                    id=make_id(config.name, link),
                    title=title,
                    organizer=config.organizer or config.display_name,
                    source_name=config.name,
                    url=link,
                    country=config.country,
                    region_tier=region_tier(config.country, config.region_tier_override),
                    listing_type=config.listing_type,
                    deadline=deadline,
                    deadline_raw=deadline_raw,
                    description=summary[:500] if summary else None,
                )
            )
        return listings
