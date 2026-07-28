from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scraper.adapters.parsing_utils import USER_AGENT, parse_deadline, parse_yyyymmdd, select_text, slugify
from scraper.models import Listing, make_id
from scraper.sources_config import SourceConfig
from scraper.tier import region_tier


class HtmlAdapter:
    def collect(self, config: SourceConfig) -> list[Listing]:
        if not config.url or config.url == "TBD":
            raise ValueError(f"Source '{config.name}' has no URL configured yet")

        item_selector = config.parser_options.get("item_selector")
        if not item_selector:
            raise ValueError(f"Source '{config.name}' is missing parser_options.item_selector")

        response = requests.get(config.url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        return extract_listings(soup.select(item_selector), config)


def extract_listings(items, config: SourceConfig) -> list[Listing]:
    opts = config.parser_options
    listings = []
    for item in items:
        title = select_text(item, opts.get("title_selector")) or ""
        if not title:
            continue

        link_selector = opts.get("link_selector")
        link_el = item.select_one(link_selector) if link_selector else item
        href = link_el.get("href") if link_el else None
        if (not href or href == "#") and opts.get("synthetic_url_from_title"):
            # Some login-gated sites (e.g. membership job boards) render every
            # card's link as a login-modal trigger with no real per-item URL.
            # A slug-based fragment keeps ids stable/unique without pretending
            # to be a deep link - clicking it just lands on the listing page.
            url = f"{config.url.split('#')[0]}#{slugify(title)}"
        elif not href:
            continue
        else:
            url = urljoin(config.url, href)

        deadline_attr = opts.get("deadline_attr")
        if deadline_attr:
            deadline_raw = item.get(deadline_attr)
            deadline = parse_yyyymmdd(deadline_raw)
        else:
            deadline_text = select_text(item, opts.get("deadline_selector"))
            deadline, deadline_raw = parse_deadline(deadline_text)

        fee_text = select_text(item, opts.get("fee_selector"))
        description = select_text(item, opts.get("description_selector"))
        eligibility = select_text(item, opts.get("eligibility_selector"))
        organizer = select_text(item, opts.get("organizer_selector")) or config.organizer or config.display_name

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
                description=description,
                eligibility=eligibility,
                raw_extra={"fee_text": fee_text} if fee_text else {},
            )
        )
    return listings
