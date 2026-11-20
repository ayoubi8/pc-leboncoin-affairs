"""How likely is it that this ad is still for sale, and how new is it?

Leboncoin ads are never removed automatically when the item sells, so old ads are often dead.
We combine the age of the ad, the last time the seller touched it (``index_date``), the seller type
and wording like "vendu" / "réservé" into a 0-100 score, and verify the best candidates against the
live ad page before alerting.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..models import Listing

# (max age in hours, score)
_CURVE = [(2, 100), (6, 92), (12, 85), (24, 75), (48, 60), (72, 45), (168, 30), (336, 18)]

SOLD_PATTERNS = [
    (re.compile(r"\bvendu(e)?\b|\bdéjà vendu|\bdeja vendu", re.I), "says sold"),
    (re.compile(r"plus disponible|n'est plus (en vente|dispo)|\bindisponible\b", re.I), "says unavailable"),
    (re.compile(r"\br[ée]serv[ée](e)?\b|\bsous (offre|r[ée]serve)\b|\ben attente de paiement\b|\ben cours de vente\b", re.I), "reserved / pending sale"),
]


def _last_sunday(year: int, month: int) -> datetime:
    day = datetime(year, month, 31 if month in (3, 10) else 30, 1)  # 01:00 UTC
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def paris_to_utc(local: datetime) -> datetime:
    """Leboncoin timestamps are Paris local time; convert to naive UTC (EU DST rules, no tzdata needed)."""
    start, end = _last_sunday(local.year, 3), _last_sunday(local.year, 10)
    offset = 2 if start <= local - timedelta(hours=1) < end else 1
    return local - timedelta(hours=offset)


def parse_paris(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return paris_to_utc(datetime.strptime(value[:19], fmt))
        except ValueError:
            continue
    return None


def _curve(hours: float) -> float:
    for limit, score in _CURVE:
        if hours <= limit:
            return float(score)
    return 8.0


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def age_hours(listing: Listing, now: Optional[datetime] = None) -> Optional[float]:
    """Hours since the ad was first published (falls back to when we first saw it)."""
    now = now or _now()
    published = parse_paris(listing.first_publication_date or "") or listing.first_seen_at
    if published is None:
        return None
    return max(0.0, (now - published).total_seconds() / 3600)


def sold_flags(listing: Listing) -> list[str]:
    text = f"{listing.subject or ''} {listing.description or ''}"
    return [label for pattern, label in SOLD_PATTERNS if pattern.search(text)]


def compute(listing: Listing, now: Optional[datetime] = None) -> dict[str, Any]:
    """Return {"score", "age_hours", "activity_age_hours", "flags"} for a listing."""
    now = now or _now()
    if listing.gone_at is not None or listing.is_active is False:
        return {"score": 0.0, "age_hours": age_hours(listing, now), "activity_age_hours": None, "flags": ["ad is gone"]}

    age = age_hours(listing, now)
    published = parse_paris(listing.first_publication_date or "") or listing.first_seen_at
    bumped = parse_paris(listing.index_date or "")
    last_activity = max([d for d in (published, bumped) if d is not None], default=None)
    activity_age = max(0.0, (now - last_activity).total_seconds() / 3600) if last_activity else age

    if age is None:
        return {"score": 50.0, "age_hours": None, "activity_age_hours": None, "flags": []}

    # 70 % how recently the seller touched it (is it alive?), 30 % how new it is (is anyone else on it?)
    score = 0.7 * _curve(activity_age if activity_age is not None else age) + 0.3 * _curve(age)
    flags = sold_flags(listing)
    if flags:
        score -= 35
    if not listing.is_pro and age > 72 and not bumped:
        score -= 8  # old private ad nobody has touched: the classic "forgot to delete"
        flags.append("old private ad, never bumped")
    if (listing.repost_count or 0) >= 2:
        score -= 6
        flags.append(f"reposted {listing.repost_count}x (hard to sell?)")
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "age_hours": round(age, 1),
        "activity_age_hours": round(activity_age, 1) if activity_age is not None else None,
        "flags": flags,
    }


def apply(listing: Listing, now: Optional[datetime] = None) -> dict[str, Any]:
    info = compute(listing, now)
    listing.freshness_score = info["score"]
    return info


def age_label(hours: Optional[float]) -> str:
    if hours is None:
        return "age unknown"
    if hours < 1:
        return f"{max(1, round(hours * 60))} min old"
    if hours < 48:
        return f"{hours:.0f} h old"
    return f"{hours / 24:.0f} days old"
