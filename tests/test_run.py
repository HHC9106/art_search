from datetime import date

import yaml

from scraper.run import run

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
