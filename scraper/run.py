from __future__ import annotations

import argparse
import json
import traceback
from datetime import date
from pathlib import Path

from scraper.adapters.base import get_adapter
from scraper.discipline_tags import auto_tag_discipline
from scraper.models import Listing
from scraper.notify import build_and_send
from scraper.sources_config import load_sources

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "docs" / "data"
LISTINGS_PATH = DATA_DIR / "listings.json"
META_PATH = DATA_DIR / "meta.json"
SOURCES_PATH = REPO_ROOT / "sources.yaml"

# Weekly cadence: 3 consecutive missed weekly checks before presuming a
# vanished listing has actually closed, rather than just being a transient
# scrape hiccup.
STALE_AFTER_DAYS = 21


def load_previous_listings(listings_path: Path) -> dict[str, Listing]:
    if not listings_path.exists():
        return {}
    raw = json.loads(listings_path.read_text(encoding="utf-8"))
    return {item["id"]: Listing.from_dict(item) for item in raw}


def _recompute_status(listing: Listing, today: date) -> None:
    if listing.deadline and listing.deadline < today:
        listing.status = "closed"
        return
    if listing.last_checked_date and listing.last_seen_date:
        stale_days = (listing.last_checked_date - listing.last_seen_date).days
        if stale_days >= STALE_AFTER_DAYS:
            listing.status = "closed"
            return
    listing.status = "open"


def run(
    send_email: bool = True,
    today: date | None = None,
    sources_path: Path | None = None,
    listings_path: Path | None = None,
    meta_path: Path | None = None,
) -> dict:
    """Runs one full scrape-normalize-publish cycle. Accepts path/today overrides
    so tests can run it against fixture sources and fixed dates without touching
    the real docs/data files or the system clock."""
    today = today or date.today()
    sources_path = sources_path or SOURCES_PATH
    listings_path = listings_path or LISTINGS_PATH
    meta_path = meta_path or META_PATH

    previous = load_previous_listings(listings_path)
    sources = load_sources(sources_path)

    merged: dict[str, Listing] = dict(previous)
    seen_ids_this_run: set[str] = set()
    successful_sources: set[str] = set()
    source_errors: dict[str, str] = {}

    for source in sources:
        if not source.enabled:
            continue
        try:
            adapter = get_adapter(source.adapter)
            fresh_listings = adapter.collect(source)
        except Exception as exc:  # noqa: BLE001 - one bad source must never kill the run
            source_errors[source.name] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            print(f"::warning::Source '{source.name}' failed: {exc}")
            continue

        successful_sources.add(source.name)
        for listing in fresh_listings:
            if not listing.discipline:
                listing.discipline = auto_tag_discipline(
                    f"{listing.title} {listing.description or ''} {listing.eligibility or ''}"
                )
            seen_ids_this_run.add(listing.id)
            existing = merged.get(listing.id)
            if existing is not None:
                listing.first_seen_date = existing.first_seen_date
                listing.notified_tier = existing.notified_tier
                listing.last_notified_date = existing.last_notified_date
            else:
                listing.first_seen_date = today
            listing.last_seen_date = today
            listing.last_checked_date = today
            merged[listing.id] = listing

    # Listings from sources that ran successfully this run but weren't
    # re-sighted: advance last_checked_date only, so _recompute_status can
    # detect staleness via the growing gap to last_seen_date.
    for listing_id, listing in merged.items():
        if listing.source_name in successful_sources and listing_id not in seen_ids_this_run:
            listing.last_checked_date = today

    new_ids = {lid for lid in seen_ids_this_run if previous.get(lid) is None}

    for listing in merged.values():
        _recompute_status(listing, today)

    ordered = [merged[lid] for lid in sorted(merged.keys())]

    if send_email:
        build_and_send(listings=ordered, new_ids=new_ids, source_errors=source_errors, today=today)

    listings_path.parent.mkdir(parents=True, exist_ok=True)
    listings_path.write_text(
        json.dumps([listing.to_dict() for listing in ordered], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    meta = {
        "last_run": today.isoformat(),
        "total_listings": len(ordered),
        "open_listings": sum(1 for listing in ordered if listing.status == "open"),
        "sources": {
            **{name: {"status": "ok"} for name in successful_sources},
            **{name: {"status": "error", "error": err} for name, err in source_errors.items()},
        },
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape, normalize, and publish art open-call listings.")
    parser.add_argument("--dry-run", action="store_true", help="Write listings.json locally but skip sending email")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    run(send_email=not args.dry_run)


if __name__ == "__main__":
    main()
