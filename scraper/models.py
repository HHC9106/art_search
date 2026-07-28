from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import Any, Optional

DATE_FIELDS = ("deadline", "first_seen_date", "last_seen_date", "last_checked_date", "last_notified_date")


def make_id(source_name: str, url: str) -> str:
    digest = hashlib.sha256(f"{source_name}:{url}".encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass
class Listing:
    id: str
    title: str
    organizer: str
    source_name: str
    url: str
    country: Optional[str] = None
    region_tier: int = 3
    discipline: list[str] = field(default_factory=list)
    listing_type: str = "open_call"  # open_call | prize | residency | grant
    deadline: Optional[date] = None
    deadline_raw: Optional[str] = None
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    fee_waiver_available: Optional[bool] = None
    prize_amount: Optional[str] = None
    eligibility: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    status: str = "open"  # open | closed
    first_seen_date: Optional[date] = None
    last_seen_date: Optional[date] = None
    last_checked_date: Optional[date] = None
    notified_tier: str = "none"  # none | month | urgent
    last_notified_date: Optional[date] = None
    raw_extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in DATE_FIELDS:
            if d[key] is not None:
                d[key] = d[key].isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Listing":
        d = dict(d)
        for key in DATE_FIELDS:
            if d.get(key):
                d[key] = date.fromisoformat(d[key])
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
