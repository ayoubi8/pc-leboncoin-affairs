"""Deal pipeline (contacted -> bought -> shipped -> sold) and learning from the outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..intelligence import pricebook
from ..logistics import landed
from ..models import Listing, Settings

STATUSES = ("contacted", "bought", "shipped", "sold", "skipped")
MIN_SAMPLES_TO_LEARN = 3


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_status(
    db: Session,
    settings: Settings,
    listing: Listing,
    status: str,
    bought_price_eur: Optional[float] = None,
    sold_price_dzd: Optional[float] = None,
) -> Listing:
    if status not in STATUSES and status != "":
        raise ValueError(f"unknown status {status!r}")
    listing.pipeline_status = status
    listing.pipeline_updated_at = _now()
    if bought_price_eur is not None:
        listing.bought_price_eur = float(bought_price_eur)
    if sold_price_dzd is not None:
        listing.sold_price_dzd = float(sold_price_dzd)
    if status == "bought" and listing.bought_price_eur is None:
        numbers = (listing.ai_verdict or {}).get("numbers") or {}
        listing.bought_price_eur = numbers.get("buy_price_eur") or listing.price_eur
    db.commit()
    calibrate(db, settings)
    return listing


def realised_profit(settings: Settings, listing: Listing) -> Optional[dict[str, float]]:
    """Real profit of a sold deal: sale price (EUR at the parallel rate) minus the landed cost of what we paid."""
    if listing.bought_price_eur is None or listing.sold_price_dzd is None:
        return None
    rate = float(settings.eur_dzd_parallel or 280)
    cost = landed.compute(settings, listing.bought_price_eur, kind=pricebook.kind_of(listing), specs=listing.specs)["total_eur"]
    revenue = listing.sold_price_dzd / rate
    return {"cost_eur": round(cost, 2), "revenue_eur": round(revenue, 2), "profit_eur": round(revenue - cost, 2),
            "margin_pct": round((revenue - cost) / cost * 100, 1) if cost else 0.0}


def calibrate(db: Session, settings: Settings) -> dict[str, Any]:
    """Learn from real outcomes: the discount sellers accept and how far resale falls below asking prices."""
    result: dict[str, Any] = {}
    bought = db.execute(
        select(Listing).where(Listing.bought_price_eur.is_not(None), Listing.price_eur.is_not(None))
    ).scalars().all()
    discounts = [(l.price_eur - l.bought_price_eur) / l.price_eur * 100 for l in bought if l.price_eur and l.price_eur > 0]
    if len(discounts) >= MIN_SAMPLES_TO_LEARN:
        settings.avg_discount_pct = round(max(0.0, min(30.0, sum(discounts) / len(discounts))), 1)
        result["avg_discount_pct"] = settings.avg_discount_pct

    sold = [l for l in bought if l.sold_price_dzd and l.dz_price_median_dzd]
    ratios = [1 - l.sold_price_dzd / l.dz_price_median_dzd for l in sold]
    if len(ratios) >= MIN_SAMPLES_TO_LEARN:
        settings.resale_haircut_pct = round(max(0.0, min(40.0, sum(ratios) / len(ratios) * 100)), 1)
        result["resale_haircut_pct"] = settings.resale_haircut_pct
    if result:
        db.commit()
    return result


def summary(db: Session, settings: Settings) -> dict[str, Any]:
    rows = db.execute(select(Listing).where(Listing.pipeline_status != "").order_by(Listing.pipeline_updated_at.desc())).scalars().all()
    total = 0.0
    sold_count = 0
    for listing in rows:
        outcome = realised_profit(settings, listing)
        if outcome:
            total += outcome["profit_eur"]
            sold_count += 1
    return {"count": len(rows), "sold": sold_count, "realised_profit_eur": round(total, 2), "rows": rows}
