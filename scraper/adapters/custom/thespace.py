from __future__ import annotations

import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from scraper.adapters.parsing_utils import USER_AGENT
from scraper.models import Listing, make_id
from scraper.sources_config import SourceConfig
from scraper.tier import region_tier

# Section headings (lowercased) worth extracting opportunities from. The page
# also has "Events and Conferences", "Resources", and a webinars section with
# the same paragraph styling but no actual open calls - excluded on purpose.
INCLUDE_SECTIONS = {"currently open for applications", "midlands opportunities"}

_DAY_MONTH_PATTERN = re.compile(
    r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)",
    re.IGNORECASE,
)


def parse_deadline(text: str | None, today: date) -> tuple[date | None, str | None]:
    """The Space writes deadlines as bare day+month with no year (e.g.
    "Deadline: 31 July"), or as non-dates ("Rolling", "various", "Ongoing").
    Assumes the current year, rolling forward to next year if that's already
    past - a reasonable default for a page updated regularly."""
    if not text:
        return None, None
    match = _DAY_MONTH_PATTERN.search(text)
    if not match:
        return None, text
    day, month_name = int(match.group(1)), match.group(2)
    try:
        candidate = datetime.strptime(f"{day} {month_name} {today.year}", "%d %B %Y").date()
    except ValueError:
        return None, text
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate, text


def extract_listings(soup, config: SourceConfig, today: date) -> list[Listing]:
    container = soup.select_one("div.single_text_col")
    if container is None:
        raise RuntimeError("Expected content container 'div.single_text_col' not found on the page")

    elements = container.find_all(["h5", "p"])
    listings: list[Listing] = []
    in_scope = False

    for index, el in enumerate(elements):
        if el.name == "h5":
            in_scope = el.get_text(strip=True).lower() in INCLUDE_SECTIONS
            continue
        if not in_scope:
            continue

        link = el.find("a", href=True)
        text = el.get_text(" ", strip=True)
        if not link or not text.startswith("➡"):
            continue

        url = link["href"]
        organizer_tag = el.find("strong")
        organizer = organizer_tag.get_text(strip=True).lstrip("➡️").strip() if organizer_tag else ""
        organizer = organizer or config.organizer or config.display_name

        title = text.lstrip("➡️").strip()
        if len(title) > 150:
            title = title[:147] + "..."

        deadline_text = None
        if index + 1 < len(elements) and elements[index + 1].name == "p":
            next_text = elements[index + 1].get_text(" ", strip=True)
            if next_text.lower().startswith("deadline") or next_text.lower() in ("ongoing", "rolling", "no deadline"):
                deadline_text = next_text
        deadline, deadline_raw = parse_deadline(deadline_text, today)

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
                description=text,
            )
        )

    return listings


def collect(config: SourceConfig) -> list[Listing]:
    response = requests.get(config.url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    return extract_listings(soup, config, date.today())
