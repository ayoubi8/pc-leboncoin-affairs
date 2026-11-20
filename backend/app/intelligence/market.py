from __future__ import annotations

from statistics import median as stat_median
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Listing

MIN_SAMPLES = 5  # comparables needed before a European reference price is trusted
MIN_PRICE = 40.0
MAX_PRICE = 12000.0


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _prices_for(db: Session, listing: Listing, key_filter) -> list[float]:
    statement = select(Listing.price_eur).where(
        Listing.id != listing.id,
        Listing.price_eur.is_not(None),
        Listing.price_eur >= MIN_PRICE,
        Listing.price_eur <= MAX_PRICE,
    )
    if key_filter is not None:
        statement = statement.where(key_filter)
    return [float(row[0]) for row in db.execute(statement).all() if row[0]]


def compute_market(db: Session, listing: Listing) -> dict[str, Any]:
    specs = listing.specs or {}
    cpu_family = specs.get("cpu_family") or ""
    ram = specs.get("ram_gb")
    storage = specs.get("storage_gb")
    brand = specs.get("brand") or listing.brand or ""

    tiers: list[tuple[str, Any]] = []
    if listing.model_key:
        tiers.append(("exact model", Listing.model_key == listing.model_key))
    if cpu_family and ram:
        tiers.append(("same CPU family + RAM", (Listing.model_key.like(f"{cpu_family}|{ram}|%"))))
    if cpu_family:
        tiers.append(("same CPU family", (Listing.model_key.like(f"{cpu_family}|%"))))
    if brand and specs.get("screen_inches"):
        tiers.append(("same brand + screen", (Listing.model_key.like(f"{brand}|{specs['screen_inches']}%"))))
    if brand:
        tiers.append(("same brand", (Listing.model_key.like(f"{brand}|%"))))

    samples: list[float] = []
    used_scope = "none"
    for scope, condition in tiers:
        found = _prices_for(db, listing, condition)
        if len(found) >= MIN_SAMPLES:
            samples, used_scope = found, scope
            break
    # No "all listings" fallback: mixing laptops, GPUs and accessories gave meaningless medians.

    if not samples:
        return {
            "low_eur": None,
            "median_eur": None,
            "high_eur": None,
            "confidence": "none",
            "samples": 0,
            "scope": "none",
            "explanation": f"Fewer than {MIN_SAMPLES} comparable listings of the same model so far, so no European reference price.",
        }

    ordered = sorted(samples)
    med = stat_median(ordered)
    low = _percentile(ordered, 0.25)
    high = _percentile(ordered, 0.75)
    if len(ordered) < 4:
        low = med * 0.88
        high = med * 1.12

    count = len(ordered)
    if count >= 8:
        confidence = "high"
    elif count >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    explanation = (
        f"{count} comparable listing(s) ({used_scope}); "
        f"market range {low:.0f}–{high:.0f} EUR, median {med:.0f} EUR."
    )
    if confidence == "low":
        explanation += " Low confidence: fewer than 4 comparables."

    return {
        "low_eur": round(low, 2),
        "median_eur": round(med, 2),
        "high_eur": round(high, 2),
        "confidence": confidence,
        "samples": count,
        "scope": used_scope,
        "explanation": explanation,
    }


def market_payload(listing: Listing, explanation: Optional[str] = None) -> dict[str, Any]:
    return {
        "low_eur": listing.market_low_eur,
        "median_eur": listing.market_median_eur,
        "high_eur": listing.market_high_eur,
        "confidence": listing.market_confidence,
        "samples": listing.market_samples or 0,
        "explanation": explanation or "",
    }
