from __future__ import annotations

from datetime import datetime

from scraper.models import Listing, make_id
from scraper.sources_config import SourceConfig
from scraper.tier import region_tier


class ManualAdapter:
    def collect(self, config: SourceConfig) -> list[Listing]:
        listings = []
        for entry in config.manual_entries:
            url = entry["url"]
            deadline = None
            if entry.get("deadline"):
                deadline = datetime.strptime(entry["deadline"], "%Y-%m-%d").date()
            country = entry.get("country", config.country)

            listings.append(
                Listing(
                    id=make_id(config.name, url),
                    title=entry["title"],
                    organizer=entry.get("organizer", config.organizer or config.display_name),
                    source_name=config.name,
                    url=url,
                    country=country,
                    region_tier=region_tier(country, entry.get("region_tier", config.region_tier_override)),
                    listing_type=entry.get("listing_type", config.listing_type),
                    deadline=deadline,
                    deadline_raw=entry.get("deadline"),
                    prize_amount=entry.get("prize_amount"),
                    eligibility=entry.get("eligibility"),
                    description=entry.get("notes"),
                )
            )
        return listings
