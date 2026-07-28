from datetime import date

import pytest

from scraper.adapters.google_search import GoogleSearchAdapter, _listings_from_response
from scraper.sources_config import SourceConfig


def make_config(**overrides):
    defaults = dict(
        name="google_search_opportunities",
        adapter="google_search",
        display_name="Google Search",
        country=None,
        listing_type="open_call",
        parser_options={"search_queries": ['"artist commission" "civic data" site:org.uk']},
    )
    defaults.update(overrides)
    return SourceConfig(**defaults)


SAMPLE_RESPONSE = {
    "items": [
        {
            "title": "Civic Data Artist Commission 2026",
            "link": "https://example.org.uk/commission",
            "snippet": "Deadline: 15 September 2026. Apply now for this civic data commission.",
            "displayLink": "example.org.uk",
        },
        {
            "title": "Another Result With No Snippet Deadline",
            "link": "https://another.example.org.uk/opportunity",
            "displayLink": "another.example.org.uk",
        },
    ]
}


def test_listings_from_response_extracts_fields():
    config = make_config()
    listings = _listings_from_response(SAMPLE_RESPONSE, config, "test query")
    assert len(listings) == 2

    first = listings[0]
    assert first.title == "Civic Data Artist Commission 2026"
    assert first.url == "https://example.org.uk/commission"
    assert first.organizer == "example.org.uk"
    assert first.deadline == date(2026, 9, 15)
    assert first.raw_extra == {"search_query": "test query"}


def test_listings_from_response_handles_missing_snippet_and_deadline():
    config = make_config()
    listings = _listings_from_response(SAMPLE_RESPONSE, config, "test query")
    second = listings[1]
    assert second.deadline is None
    assert second.description is None


def test_listings_from_response_skips_items_missing_title_or_link():
    response = {"items": [{"title": "", "link": "https://example.org"}, {"title": "No link"}]}
    config = make_config()
    assert _listings_from_response(response, config, "q") == []


def test_listings_from_response_handles_empty_or_missing_items():
    config = make_config()
    assert _listings_from_response({}, config, "q") == []
    assert _listings_from_response({"items": []}, config, "q") == []


def test_collect_raises_clearly_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)
    config = make_config()
    with pytest.raises(ValueError, match="GOOGLE_SEARCH_API_KEY"):
        GoogleSearchAdapter().collect(config)


def test_collect_raises_clearly_when_no_queries_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "fake-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "fake-engine-id")
    config = make_config(parser_options={})
    with pytest.raises(ValueError, match="search_queries"):
        GoogleSearchAdapter().collect(config)


def test_collect_continues_past_a_failing_query(monkeypatch):
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "fake-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "fake-engine-id")

    calls = []

    class FakeResponse:
        def __init__(self, query):
            self._query = query

        def raise_for_status(self):
            if self._query == "bad query":
                raise RuntimeError("simulated API error")

        def json(self):
            return SAMPLE_RESPONSE

    def fake_get(url, params, timeout):
        calls.append(params["q"])
        return FakeResponse(params["q"])

    monkeypatch.setattr("scraper.adapters.google_search.requests.get", fake_get)

    config = make_config(parser_options={"search_queries": ["bad query", "good query"]})
    listings = GoogleSearchAdapter().collect(config)

    assert calls == ["bad query", "good query"]
    assert len(listings) == 2  # only the good query's results survived
