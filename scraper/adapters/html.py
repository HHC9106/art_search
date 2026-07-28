from __future__ import annotations

import hashlib
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

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

        opts = config.parser_options
        if not opts.get("single_page") and not opts.get("item_selector"):
            raise ValueError(f"Source '{config.name}' is missing parser_options.item_selector")

        response = requests.get(config.url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        if opts.get("single_page"):
            return [extract_single_page_listing(soup, config)]

        return extract_listings(soup.select(opts["item_selector"]), config)


def extract_single_page_listing(soup, config: SourceConfig) -> Listing:
    """For single-institution pages with no repeatable listing structure (e.g.
    an "Open Calls" section that's plain CMS prose): treats the whole page as
    one watched item. Hashes a content region so run.py can detect "this page
    changed since we last checked" even though title/deadline may not be
    reliably parseable, and surface that as worth a manual look."""
    opts = config.parser_options

    title = select_text(soup, opts.get("title_selector")) or config.display_name
    if not title:
        title = soup.title.get_text(strip=True) if soup.title else ""

    deadline_text = select_text(soup, opts.get("deadline_selector"))
    deadline, deadline_raw = parse_deadline(deadline_text)

    content_el = soup.select_one(opts.get("content_selector", "body")) or soup
    content_text = content_el.get_text(" ", strip=True)
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()[:16]

    description = select_text(soup, opts.get("description_selector")) or content_text[:500]
    eligibility = select_text(soup, opts.get("eligibility_selector"))

    return Listing(
        id=make_id(config.name, config.url),
        title=title,
        organizer=config.organizer or config.display_name,
        source_name=config.name,
        url=config.url,
        country=config.country,
        region_tier=region_tier(config.country, config.region_tier_override),
        listing_type=config.listing_type,
        deadline=deadline,
        deadline_raw=deadline_raw,
        description=description,
        eligibility=eligibility,
        raw_extra={"content_hash": content_hash},
    )


def extract_listings(items, config: SourceConfig) -> list[Listing]:
    opts = config.parser_options
    listings = []
    for item in items:
        title = select_text(item, opts.get("title_selector")) or ""
        if not title:
            continue

        organizer = select_text(item, opts.get("organizer_selector")) or config.organizer or config.display_name

        link_selector = opts.get("link_selector")
        link_el = item.select_one(link_selector) if link_selector else item
        href = link_el.get("href") if link_el else None
        if not href and opts.get("fallback_link_selector"):
            # Some sites link to a real external URL for most items but omit
            # it for a few - fall back to another selector (e.g. the site's
            # own internal detail page) rather than dropping the listing.
            fallback_el = item.select_one(opts["fallback_link_selector"])
            href = fallback_el.get("href") if fallback_el else None
        if not href or href == "#":
            if opts.get("google_search_link"):
                # Login-gated with no usable real/synthetic destination at
                # all - send the user to a Google search for the title +
                # organizer instead, which usually surfaces the actual
                # organizer's page for the opportunity.
                url = f"https://www.google.com/search?q={quote_plus(f'{title} {organizer}'.strip())}"
            elif opts.get("synthetic_url_from_title"):
                # Some login-gated sites (e.g. membership job boards) render
                # every card's link as a login-modal trigger with no real
                # per-item URL. A slug-based fragment keeps ids stable/unique
                # without pretending to be a deep link - clicking it just
                # lands on the listing page.
                #
                # public_url lets this point at the human-facing search page
                # instead of config.url, which for some sources is a raw AJAX
                # fragment endpoint (no page chrome/CSS - looks broken if a
                # user actually navigates to it) rather than a real browsable
                # page. Built from scheme+host+path only (no query/fragment)
                # so tweaking query params (e.g. category filters) later never
                # changes existing ids and creates duplicates.
                parts = urlsplit(opts.get("public_url") or config.url)
                base_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
                url = f"{base_url}#{slugify(title)}"
            else:
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
