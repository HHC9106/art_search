from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.adapters.custom.thespace import extract_listings, parse_deadline
from scraper.sources_config import SourceConfig

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 7, 20)


def make_config():
    return SourceConfig(
        name="thespace",
        adapter="custom",
        display_name="The Space",
        organizer="The Space",
        url="https://www.thespace.org/resource/news-and-opportunities-from-across-the-sector/",
        listing_type="open_call",
    )


def load_soup():
    html = (FIXTURES / "thespace_sample.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "lxml")


def test_only_included_sections_are_extracted():
    listings = extract_listings(load_soup(), make_config(), TODAY)
    titles = [l.title for l in listings]
    assert len(listings) == 3
    assert any("Fine Acts" in t for t in titles)
    assert any("Doc Society" in t for t in titles)
    assert any("Belgrade Theatre" in t for t in titles)
    # Events/Conferences and Resources sections must be excluded
    assert not any("Museums Association" in t for t in titles)
    assert not any("self-publishing" in t for t in titles)


def test_organizer_and_url_extracted_correctly():
    listings = extract_listings(load_soup(), make_config(), TODAY)
    fine_acts = next(l for l in listings if "Fine Acts" in l.title)
    assert fine_acts.organizer == "Fine Acts"
    assert fine_acts.url == "https://fineacts.co/ted-posca-residency"


def test_bare_day_month_deadline_assumes_current_year():
    listings = extract_listings(load_soup(), make_config(), TODAY)
    fine_acts = next(l for l in listings if "Fine Acts" in l.title)
    assert fine_acts.deadline == date(2026, 7, 31)


def test_non_date_deadline_text_falls_back_to_raw():
    listings = extract_listings(load_soup(), make_config(), TODAY)
    doc_society = next(l for l in listings if "Doc Society" in l.title)
    assert doc_society.deadline is None
    assert doc_society.deadline_raw == "Deadline: various"


def test_parse_deadline_rolls_forward_to_next_year_if_already_past():
    deadline, raw = parse_deadline("Deadline: 1 January", today=date(2026, 7, 20))
    assert deadline == date(2027, 1, 1)
    assert raw == "Deadline: 1 January"


def test_parse_deadline_same_year_if_still_upcoming():
    deadline, raw = parse_deadline("Deadline: 19 August", today=date(2026, 7, 20))
    assert deadline == date(2026, 8, 19)


def test_parse_deadline_handles_none_and_non_matching_text():
    assert parse_deadline(None, TODAY) == (None, None)
    assert parse_deadline("Rolling", TODAY) == (None, "Rolling")
