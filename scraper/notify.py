from __future__ import annotations

import argparse
import json
import os
import smtplib
from dataclasses import dataclass
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from scraper.models import Listing
from scraper.tier import TIER_LEVELS

HEADS_UP_DAYS = 30
URGENT_DAYS = 7

TIER_LABELS = {"top": "Top", "high": "High", "medium": "Medium", "low": "Low"}

REPO_ROOT = Path(__file__).resolve().parent.parent
LISTINGS_PATH = REPO_ROOT / "docs" / "data" / "listings.json"


@dataclass
class DigestSections:
    new_listings: list[Listing]
    heads_up: list[Listing]
    urgent: list[Listing]
    source_errors: dict[str, str]

    @property
    def is_empty(self) -> bool:
        return not (self.new_listings or self.heads_up or self.urgent or self.source_errors)


def compute_sections(
    listings: list[Listing],
    new_ids: set[str],
    source_errors: dict[str, str],
    today: date,
) -> DigestSections:
    """Mutates notified_tier/last_notified_date in place on listings that cross
    a threshold this run, so the same listing is only ever flagged once per tier
    even though the scraper runs weekly."""
    new_listings = [listing for listing in listings if listing.id in new_ids]
    heads_up: list[Listing] = []
    urgent: list[Listing] = []

    for listing in listings:
        if listing.status != "open" or listing.deadline is None:
            continue
        days_left = (listing.deadline - today).days
        if days_left < 0:
            continue
        if days_left <= URGENT_DAYS and listing.notified_tier != "urgent":
            urgent.append(listing)
            listing.notified_tier = "urgent"
            listing.last_notified_date = today
        elif days_left <= HEADS_UP_DAYS and listing.notified_tier not in ("month", "urgent"):
            heads_up.append(listing)
            listing.notified_tier = "month"
            listing.last_notified_date = today

    return DigestSections(new_listings=new_listings, heads_up=heads_up, urgent=urgent, source_errors=source_errors)


def render_html(sections: DigestSections, today: date) -> str:
    def render_group(title: str, listings: list[Listing]) -> str:
        if not listings:
            return ""
        by_tier: dict[str, list[Listing]] = {}
        for listing in listings:
            by_tier.setdefault(listing.region_tier, []).append(listing)

        parts = [f"<h2>{title}</h2>"]
        for tier in sorted(by_tier, key=lambda t: TIER_LEVELS.index(t) if t in TIER_LEVELS else len(TIER_LEVELS)):
            parts.append(f"<h3>{TIER_LABELS.get(tier, tier.title())}</h3><ul>")
            for listing in sorted(by_tier[tier], key=lambda l: l.deadline or date.max):
                deadline_str = listing.deadline.isoformat() if listing.deadline else "no deadline"
                parts.append(
                    f'<li><a href="{listing.url}">{listing.title}</a> — {listing.organizer} '
                    f"(deadline: {deadline_str})</li>"
                )
            parts.append("</ul>")
        return "".join(parts)

    html = [f"<html><body><p>Art open-call digest — {today.isoformat()}</p>"]
    html.append(render_group("Urgent — deadline within 7 days", sections.urgent))
    html.append(render_group(f"Heads up — deadline within {HEADS_UP_DAYS} days", sections.heads_up))
    html.append(render_group("New this run", sections.new_listings))

    if sections.source_errors:
        html.append("<h2>Source health</h2><ul>")
        for name, err in sections.source_errors.items():
            html.append(f"<li>{name}: {err}</li>")
        html.append("</ul>")

    html.append("</body></html>")
    return "".join(html)


def send_email(html_body: str, subject: str) -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = email_to
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_address, gmail_password)
        server.send_message(msg)


def build_and_send(
    listings: list[Listing],
    new_ids: set[str],
    source_errors: dict[str, str],
    today: date,
) -> DigestSections:
    sections = compute_sections(listings, new_ids, source_errors, today)
    if sections.is_empty:
        print("Digest empty (no new/heads-up/urgent/errors) — skipping email.")
        return sections

    html_body = render_html(sections, today)
    subject = (
        f"Art open calls — {len(sections.new_listings)} new, "
        f"{len(sections.urgent)} urgent ({today.isoformat()})"
    )

    try:
        send_email(html_body, subject)
    except Exception as exc:  # noqa: BLE001 - a failed send must never fail the whole run
        print(f"::warning::Failed to send email digest: {exc}")

    return sections


def _load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and optionally send the email digest, for local testing.")
    parser.add_argument("--dry-run", action="store_true", help="Render the digest but don't send anything")
    parser.add_argument("--preview-file", type=str, default=None, help="Write the rendered HTML to this file")
    parser.add_argument("--send-test", action="store_true", help="Actually send one real test email")
    args = parser.parse_args()

    _load_dotenv_if_present()

    raw = json.loads(LISTINGS_PATH.read_text(encoding="utf-8")) if LISTINGS_PATH.exists() else []
    listings = [Listing.from_dict(item) for item in raw]
    today = date.today()

    sections = compute_sections(listings, new_ids=set(), source_errors={}, today=today)
    html_body = render_html(sections, today)

    if args.preview_file:
        Path(args.preview_file).write_text(html_body, encoding="utf-8")
        print(f"Wrote preview to {args.preview_file}")

    if args.send_test:
        send_email(html_body, subject=f"[TEST] Art open calls digest ({today.isoformat()})")
        print("Test email sent.")
    elif args.dry_run:
        print("Dry run complete, no email sent.")


if __name__ == "__main__":
    main()
