from datetime import date, timedelta

from scraper.models import Listing, make_id
from scraper.notify import compute_sections, render_html

TODAY = date(2026, 7, 27)


def make_listing(url, days_left=None, region_tier="top", notified_tier="none", status="open"):
    deadline = TODAY + timedelta(days=days_left) if days_left is not None else None
    return Listing(
        id=make_id("s", url),
        title=f"Listing {url}",
        organizer="Org",
        source_name="s",
        url=url,
        region_tier=region_tier,
        deadline=deadline,
        notified_tier=notified_tier,
        status=status,
    )


def test_new_listing_is_flagged_new():
    listing = make_listing("new", days_left=100)
    sections = compute_sections([listing], new_ids={listing.id}, source_errors={}, today=TODAY)
    assert sections.new_listings == [listing]
    assert sections.heads_up == []
    assert sections.urgent == []


def test_urgent_within_7_days():
    listing = make_listing("urgent", days_left=3)
    sections = compute_sections([listing], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.urgent == [listing]
    assert listing.notified_tier == "urgent"
    assert listing.last_notified_date == TODAY


def test_heads_up_within_30_days_but_not_7():
    listing = make_listing("heads_up", days_left=20)
    sections = compute_sections([listing], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.heads_up == [listing]
    assert listing.notified_tier == "month"


def test_already_urgent_is_not_flagged_again():
    listing = make_listing("already_urgent", days_left=2, notified_tier="urgent")
    sections = compute_sections([listing], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.urgent == []
    assert sections.heads_up == []


def test_already_month_is_not_bumped_back_to_heads_up_but_can_still_go_urgent():
    listing = make_listing("was_month_now_urgent", days_left=5, notified_tier="month")
    sections = compute_sections([listing], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.urgent == [listing]
    assert listing.notified_tier == "urgent"


def test_closed_or_no_deadline_listings_are_never_flagged():
    closed = make_listing("closed", days_left=3, status="closed")
    no_deadline = make_listing("no_deadline", days_left=None)
    sections = compute_sections([closed, no_deadline], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.urgent == []
    assert sections.heads_up == []


def test_past_deadline_is_not_flagged():
    listing = make_listing("past", days_left=-1)
    sections = compute_sections([listing], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.urgent == []
    assert sections.heads_up == []


def test_is_empty_true_only_when_nothing_to_report():
    empty = compute_sections([], new_ids=set(), source_errors={}, today=TODAY)
    assert empty.is_empty

    with_error = compute_sections([], new_ids=set(), source_errors={"src": "boom"}, today=TODAY)
    assert not with_error.is_empty


def test_render_html_includes_titles_and_source_errors():
    urgent = make_listing("urgent", days_left=2)
    sections = compute_sections([urgent], new_ids=set(), source_errors={"broken": "HTTPError: 403"}, today=TODAY)
    html = render_html(sections, TODAY)
    assert "Listing urgent" in html
    assert "broken: HTTPError: 403" in html
    assert ">Top<" in html


def test_manual_reminders_make_sections_non_empty_and_render():
    reminders = [{"name": "Blocked Source", "url": "https://example.org/blocked", "notes": "confirmed blocked"}]
    sections = compute_sections([], new_ids=set(), source_errors={}, today=TODAY, manual_reminders=reminders)
    assert not sections.is_empty
    html = render_html(sections, TODAY)
    assert "Blocked Source" in html
    assert "confirmed blocked" in html


def test_no_manual_reminders_defaults_to_empty_list():
    sections = compute_sections([], new_ids=set(), source_errors={}, today=TODAY)
    assert sections.manual_reminders == []
    assert sections.is_empty
