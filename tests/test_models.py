from datetime import date

from scraper.models import Listing, make_id


def test_make_id_is_stable_for_same_source_and_url():
    assert make_id("a_n_opportunities", "https://example.org/x") == make_id(
        "a_n_opportunities", "https://example.org/x"
    )


def test_make_id_differs_by_source_or_url():
    base = make_id("source_a", "https://example.org/x")
    assert base != make_id("source_b", "https://example.org/x")
    assert base != make_id("source_a", "https://example.org/y")


def test_to_dict_from_dict_roundtrip_preserves_dates_and_lists():
    listing = Listing(
        id=make_id("s", "u"),
        title="Test Prize",
        organizer="Test Org",
        source_name="s",
        url="u",
        country="UK",
        region_tier=1,
        discipline=["painting", "sculpture"],
        listing_type="prize",
        deadline=date(2026, 9, 1),
        prize_amount="£2,000",
        first_seen_date=date(2026, 7, 1),
        last_seen_date=date(2026, 7, 27),
        notified_tier="month",
        last_notified_date=date(2026, 7, 20),
        raw_extra={"fee_text": "£10"},
    )

    restored = Listing.from_dict(listing.to_dict())

    assert restored == listing


def test_from_dict_ignores_unknown_fields():
    payload = {
        "id": "abc",
        "title": "T",
        "organizer": "O",
        "source_name": "s",
        "url": "u",
        "some_future_field": "ignored",
    }
    listing = Listing.from_dict(payload)
    assert listing.id == "abc"
    assert listing.status == "open"  # default preserved
