from datetime import date

import yaml

from scraper.models import Listing, make_id
from scraper.run import compute_manual_reminders, dedupe_by_url, run
from scraper.sources_config import load_sources

WEEK_1 = date(2026, 7, 6)
WEEK_2 = date(2026, 7, 13)  # +7 days: within staleness grace period
WEEK_4 = date(2026, 7, 27)  # +21 days from WEEK_1: staleness threshold reached


def write_sources(path, manual_entries):
    sources = [
        {
            "name": "manual_test_source",
            "adapter": "manual",
            "enabled": True,
            "manual_entries": manual_entries,
        }
    ]
    path.write_text(yaml.safe_dump(sources), encoding="utf-8")


def entry(url, country="UK", deadline="2026-12-01"):
    return {"title": f"Listing {url}", "organizer": "Org", "country": country, "url": url, "deadline": deadline}


def test_first_run_creates_listings_with_first_seen_date(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    write_sources(sources_path, [entry("a"), entry("b")])

    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
    )

    assert meta["total_listings"] == 2
    assert meta["open_listings"] == 2
    assert meta["sources"]["manual_test_source"]["status"] == "ok"

    saved = {item["id"]: item for item in __import__("json").loads(listings_path.read_text())}
    assert all(item["first_seen_date"] == WEEK_1.isoformat() for item in saved.values())
    assert all(item["status"] == "open" for item in saved.values())


def test_second_run_preserves_first_seen_and_adds_new(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    write_sources(sources_path, [entry("a"), entry("b")])
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    # Week 2: "b" disappeared from the source, "c" is new.
    write_sources(sources_path, [entry("a"), entry("c")])
    run(send_email=False, today=WEEK_2, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = {item["title"]: item for item in json.loads(listings_path.read_text())}

    assert saved["Listing a"]["first_seen_date"] == WEEK_1.isoformat()
    assert saved["Listing a"]["last_seen_date"] == WEEK_2.isoformat()
    assert saved["Listing c"]["first_seen_date"] == WEEK_2.isoformat()

    # "b" was only 7 days stale (< 21-day threshold) - still presumed open.
    assert saved["Listing b"]["status"] == "open"
    assert saved["Listing b"]["last_seen_date"] == WEEK_1.isoformat()
    assert saved["Listing b"]["last_checked_date"] == WEEK_2.isoformat()


def test_listing_closes_after_staleness_threshold(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    write_sources(sources_path, [entry("a"), entry("b")])
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    write_sources(sources_path, [entry("a")])  # "b" never comes back
    run(send_email=False, today=WEEK_4, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = {item["title"]: item for item in json.loads(listings_path.read_text())}
    assert saved["Listing b"]["status"] == "closed"
    assert saved["Listing a"]["status"] == "open"


def test_past_deadline_closes_regardless_of_staleness(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    write_sources(sources_path, [entry("expired", deadline="2026-01-01")])
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = json.loads(listings_path.read_text())
    assert saved[0]["status"] == "closed"


def test_discipline_is_auto_tagged_from_title_when_not_provided(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    write_sources(
        sources_path,
        [
            {
                "title": "Open call for new media art and civic tech projects",
                "organizer": "Org",
                "country": "UK",
                "url": "a",
                "deadline": "2026-12-01",
            }
        ],
    )
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = json.loads(listings_path.read_text())
    assert saved[0]["discipline"] == ["civic_tech", "new_media_art"]


def test_explicit_manual_discipline_is_not_overwritten(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    manual_entry = entry("a")
    manual_entry["discipline"] = ["data_art"]
    manual_entry["title"] = "New media art prize"  # would auto-tag differently if not respected

    write_sources(sources_path, [manual_entry])
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = json.loads(listings_path.read_text())
    assert saved[0]["discipline"] == ["data_art"]


def test_cadence_filters_sources_by_frequency(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    sources = [
        {
            "name": "weekly_source",
            "adapter": "manual",
            "enabled": True,
            "frequency": "weekly",
            "manual_entries": [entry("weekly-item")],
        },
        {
            "name": "quarterly_source",
            "adapter": "manual",
            "enabled": True,
            "frequency": "quarterly",
            "manual_entries": [entry("quarterly-item")],
        },
    ]
    sources_path.write_text(yaml.safe_dump(sources), encoding="utf-8")

    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
        cadence="weekly",
    )
    assert meta["total_listings"] == 1
    assert "weekly_source" in meta["sources"]
    assert "quarterly_source" not in meta["sources"]

    meta = run(
        send_email=False,
        today=WEEK_2,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
        cadence="quarterly",
    )
    # both persisted now - weekly_source's listing carried over from before, plus the quarterly one added
    assert meta["total_listings"] == 2
    assert "quarterly_source" in meta["sources"]
    assert "weekly_source" not in meta["sources"]  # not re-run this time


def test_content_hash_change_resurfaces_listing_as_new(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    def write_watch_source(content_hash):
        manual_entry = entry("watch-page")
        manual_entry["raw_extra"] = {"content_hash": content_hash}
        write_sources(sources_path, [manual_entry])

    write_watch_source("hash-v1")
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    saved = json.loads(listings_path.read_text())
    assert saved[0]["first_seen_date"] == WEEK_1.isoformat()
    original_id = saved[0]["id"]

    # Quarter later: page content unchanged -> first_seen_date should NOT reset.
    write_watch_source("hash-v1")
    run(send_email=False, today=WEEK_4, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)
    saved = json.loads(listings_path.read_text())
    assert saved[0]["first_seen_date"] == WEEK_1.isoformat()

    # Page content changed -> should resurface as "new" (first_seen_date resets).
    write_watch_source("hash-v2")
    run(send_email=False, today=WEEK_4, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)
    saved = json.loads(listings_path.read_text())
    assert saved[0]["first_seen_date"] == WEEK_4.isoformat()
    assert saved[0]["id"] == original_id  # id stable throughout (same source+url)


def make_listing(source_name, url, title="Title"):
    return Listing(id=make_id(source_name, url), title=title, organizer="Org", source_name=source_name, url=url)


def test_dedupe_by_url_collapses_same_url_across_sources():
    same_url = "https://real-organizer.example/apply"
    a = make_listing("thespace", same_url, title="From The Space")
    b = make_listing("artquest_opportunities", same_url, title="From Art Quest")
    unrelated = make_listing("artrabbit_opportunities", "https://other.example/apply", title="Unrelated")

    result = dedupe_by_url({a.id: a, b.id: b, unrelated.id: unrelated})

    assert len(result) == 2
    kept_titles = {listing.title for listing in result.values()}
    assert "Unrelated" in kept_titles
    assert len(kept_titles & {"From The Space", "From Art Quest"}) == 1  # only one of the two survives


def test_dedupe_by_url_is_case_and_trailing_slash_insensitive():
    a = make_listing("thespace", "https://Real-Organizer.example/Apply/")
    b = make_listing("artquest_opportunities", "https://real-organizer.example/apply")

    result = dedupe_by_url({a.id: a, b.id: b})
    assert len(result) == 1


def test_dedupe_by_url_leaves_unique_urls_untouched():
    a = make_listing("s1", "https://one.example")
    b = make_listing("s2", "https://two.example")
    result = dedupe_by_url({a.id: a, b.id: b})
    assert len(result) == 2


def test_run_dedupes_same_url_scraped_by_two_sources(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    shared_entry_a = entry("https://real-organizer.example/apply")
    shared_entry_a["title"] = "New media art open call (from source A)"
    shared_entry_b = entry("https://real-organizer.example/apply")
    shared_entry_b["title"] = "New media art open call (from source B)"

    sources = [
        {"name": "source_a", "adapter": "manual", "enabled": True, "manual_entries": [shared_entry_a]},
        {"name": "source_b", "adapter": "manual", "enabled": True, "manual_entries": [shared_entry_b]},
    ]
    sources_path.write_text(yaml.safe_dump(sources), encoding="utf-8")

    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
    )

    assert meta["total_listings"] == 1


def test_strong_filter_applies_only_to_flagged_aggregator_sources(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    irrelevant = entry("irrelevant")
    irrelevant["title"] = "Oil painting exhibition open call"

    sources = [
        {
            "name": "aggregator_source",
            "adapter": "manual",
            "enabled": True,
            "apply_relevance_filter": True,
            "manual_entries": [irrelevant],
        },
        {
            "name": "curated_source",
            "adapter": "manual",
            "enabled": True,
            "apply_relevance_filter": False,
            "manual_entries": [entry("curated-irrelevant-but-kept")],
        },
    ]
    sources_path.write_text(yaml.safe_dump(sources), encoding="utf-8")

    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
    )

    import json

    saved = {item["source_name"] for item in json.loads(listings_path.read_text())}
    assert saved == {"curated_source"}  # aggregator_source's irrelevant listing was dropped
    assert meta["total_listings"] == 1


def test_excluded_keyword_listings_are_dropped(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    pottery_entry = entry("pottery-item")
    pottery_entry["title"] = "Pottery open call for ceramicists"
    relevant_entry = entry("relevant-item")
    relevant_entry["title"] = "New media art open call"

    write_sources(sources_path, [pottery_entry, relevant_entry])
    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
    )

    import json

    saved_titles = {item["title"] for item in json.loads(listings_path.read_text())}
    assert saved_titles == {"New media art open call"}
    assert meta["total_listings"] == 1


def test_excluded_keyword_removes_previously_saved_listing_too(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    # First run: "pottery" isn't excluded yet in this test's config (default
    # shipped exclude_keywords.yaml IS active regardless, so use a term not on
    # that list to prove removal happens on the *next* run once it matches).
    entry_a = entry("a")
    entry_a["title"] = "Knitting circle open call"
    write_sources(sources_path, [entry_a])
    run(send_email=False, today=WEEK_1, sources_path=sources_path, listings_path=listings_path, meta_path=meta_path)

    import json

    assert len(json.loads(listings_path.read_text())) == 1


def test_manual_reminders_only_surface_on_quarterly_or_all_cadence(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "blocked_quarterly_source",
                    "adapter": "html",
                    "enabled": False,
                    "frequency": "quarterly",
                    "url": "https://example.org/blocked",
                    "display_name": "Blocked Source",
                    "notes": "confirmed blocked",
                },
                {
                    "name": "blocked_weekly_source",
                    "adapter": "html",
                    "enabled": False,
                    "frequency": "weekly",
                    "url": "https://example.org/tbd",
                    "display_name": "Not Yet Configured",
                },
            ]
        ),
        encoding="utf-8",
    )
    sources = load_sources(sources_path)

    assert compute_manual_reminders(sources, "weekly") == []
    assert compute_manual_reminders(sources, "quarterly") == [
        {"name": "Blocked Source", "url": "https://example.org/blocked", "notes": "confirmed blocked"}
    ]
    assert compute_manual_reminders(sources, "all") == [
        {"name": "Blocked Source", "url": "https://example.org/blocked", "notes": "confirmed blocked"}
    ]


def test_broken_source_does_not_crash_the_run(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    listings_path = tmp_path / "listings.json"
    meta_path = tmp_path / "meta.json"

    sources = [
        {"name": "good_manual", "adapter": "manual", "enabled": True, "manual_entries": [entry("a")]},
        {"name": "bad_html", "adapter": "html", "enabled": True, "url": "TBD", "parser_options": {}},
    ]
    sources_path.write_text(yaml.safe_dump(sources), encoding="utf-8")

    meta = run(
        send_email=False,
        today=WEEK_1,
        sources_path=sources_path,
        listings_path=listings_path,
        meta_path=meta_path,
    )

    assert meta["sources"]["good_manual"]["status"] == "ok"
    assert meta["sources"]["bad_html"]["status"] == "error"
    assert meta["total_listings"] == 1
