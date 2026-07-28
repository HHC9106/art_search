from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.adapters.html import extract_listings
from scraper.adapters.parsing_utils import parse_deadline
from scraper.sources_config import SourceConfig

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_deadline_handles_common_formats():
    assert parse_deadline("Deadline: 15 September 2026")[0] == date(2026, 9, 15)
    assert parse_deadline("Deadline: 2026-10-01")[0] == date(2026, 10, 1)


def test_parse_deadline_falls_back_to_raw_text_when_unparseable():
    deadline, raw = parse_deadline("Rolling deadline, no fixed date")
    assert deadline is None
    assert raw == "Rolling deadline, no fixed date"


def test_parse_deadline_handles_none():
    assert parse_deadline(None) == (None, None)


def test_html_extraction_from_fixture_page():
    html = (FIXTURES / "sample_listing_page.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    config = SourceConfig(
        name="fixture_source",
        adapter="html",
        organizer="Fixture Org",
        country="UK",
        url="https://example.org/opportunities",
        parser_options={
            "item_selector": ".opportunity",
            "title_selector": ".op-title",
            "link_selector": ".op-title a",
            "deadline_selector": ".op-deadline",
            "fee_selector": ".op-fee",
            "eligibility_selector": ".op-eligibility",
            "description_selector": ".op-desc",
        },
    )

    listings = extract_listings(soup.select(config.parser_options["item_selector"]), config)

    assert len(listings) == 3
    assert listings[0].title == "Open Call: Emerging Painters"
    assert listings[0].url == "https://example.org/opportunities/1"
    assert listings[0].deadline == date(2026, 9, 15)
    assert listings[0].region_tier == 1
    assert listings[0].raw_extra == {"fee_text": "Entry fee: £12"}
    assert listings[0].eligibility == "UK residents only, aged 18-35"

    assert listings[1].deadline == date(2026, 10, 1)
    assert listings[1].eligibility is None  # no eligibility_selector match for this item

    # third item has no deadline selector match -> deadline stays None, no crash
    assert listings[2].deadline is None
