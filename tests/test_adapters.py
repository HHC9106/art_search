from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.adapters.html import extract_listings
from scraper.adapters.parsing_utils import parse_deadline, parse_yyyymmdd, slugify
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


def test_parse_yyyymmdd():
    assert parse_yyyymmdd("20260729") == date(2026, 7, 29)
    assert parse_yyyymmdd(None) is None
    assert parse_yyyymmdd("not-a-date") is None
    assert parse_yyyymmdd("2026-07-29") is None  # only the bare digit form is supported


def test_slugify():
    assert slugify("Online Drawing Development Year") == "online-drawing-development-year"
    assert slugify("  Multiple   Spaces & Punctuation! ") == "multiple-spaces-punctuation"


def test_html_extraction_with_deadline_attr_like_artrabbit():
    html = """
    <div class="artopp" data-d="20260729">
      <h2><a href="/artist-opportunities/example">Example Open Call</a></h2>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    config = SourceConfig(
        name="artrabbit_test",
        adapter="html",
        organizer="ArtRabbit",
        url="https://www.artrabbit.com/artist-opportunities",
        parser_options={
            "item_selector": "div.artopp",
            "title_selector": "h2 a",
            "link_selector": "h2 a",
            "deadline_attr": "data-d",
        },
    )
    listings = extract_listings(soup.select("div.artopp"), config)
    assert len(listings) == 1
    assert listings[0].deadline == date(2026, 7, 29)
    assert listings[0].deadline_raw == "20260729"
    assert listings[0].url == "https://www.artrabbit.com/artist-opportunities/example"


def test_html_extraction_synthetic_url_for_login_gated_links():
    html = """
    <div class="article-list-item">
      <h3 class="article-title"><a class="article-heading-link" href="#">Example Award</a></h3>
      <p class="article-name">Example Org</p>
    </div>
    <div class="article-list-item">
      <h3 class="article-title"><a class="article-heading-link" href="#">Another Award</a></h3>
      <p class="article-name">Another Org</p>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    config = SourceConfig(
        name="artistsnow_test",
        adapter="html",
        organizer="Artists Now",
        url="https://www.artistsnow.com/opportunities.html",
        parser_options={
            "item_selector": ".article-list-item",
            "title_selector": ".article-title a",
            "link_selector": ".article-title a",
            "organizer_selector": ".article-name",
            "synthetic_url_from_title": True,
        },
    )
    listings = extract_listings(soup.select(".article-list-item"), config)
    assert len(listings) == 2
    # distinct synthetic urls -> distinct ids, despite identical href="#" on both
    assert listings[0].url != listings[1].url
    assert listings[0].url == "https://www.artistsnow.com/opportunities.html#example-award"
    assert listings[0].organizer == "Example Org"
    assert listings[0].id != listings[1].id
