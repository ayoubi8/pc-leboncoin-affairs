"""Health, deal pipeline, price book and availability endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..intelligence import analyze, dz_market, freshness
from ..models import DzPrice, Listing
from ..notify import pipeline, system
from ..scraping import leboncoin
from .helpers import get_settings, listing_card

router = APIRouter(prefix="/api", tags=["ops"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _listing(db: Session, listing_id: int) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


# ---------------------------------------------------------------- health
@router.get("/health/system")
def system_health(db: Session = Depends(get_db)) -> dict:
    return system.compute_health(db, get_settings(db))


# ---------------------------------------------------------------- pipeline
class PipelineUpdate(BaseModel):
    status: str
    bought_price_eur: Optional[float] = None
    sold_price_dzd: Optional[float] = None


@router.patch("/listings/{listing_id}/pipeline")
def update_pipeline(listing_id: int, payload: PipelineUpdate, db: Session = Depends(get_db)) -> dict:
    settings = get_settings(db)
    listing = _listing(db, listing_id)
    try:
        pipeline.set_status(db, settings, listing, payload.status, payload.bought_price_eur, payload.sold_price_dzd)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": listing.pipeline_status, "realised": pipeline.realised_profit(settings, listing)}


@router.get("/pipeline")
def pipeline_board(db: Session = Depends(get_db)) -> dict:
    settings = get_settings(db)
    data = pipeline.summary(db, settings)
    rows = []
    for listing in data["rows"]:
        card = listing_card(listing).model_dump(mode="json")
        card.update({
            "pipeline_status": listing.pipeline_status,
            "bought_price_eur": listing.bought_price_eur,
            "sold_price_dzd": listing.sold_price_dzd,
            "realised": pipeline.realised_profit(settings, listing),
        })
        rows.append(card)
    return {
        "count": data["count"], "sold": data["sold"], "realised_profit_eur": data["realised_profit_eur"],
        "learned": {"avg_discount_pct": settings.avg_discount_pct, "resale_haircut_pct": settings.resale_haircut_pct},
        "rows": rows,
    }


# ---------------------------------------------------------------- availability
@router.post("/listings/{listing_id}/recheck")
def recheck_online(listing_id: int, db: Session = Depends(get_db)) -> dict:
    """Ask Leboncoin right now whether the ad is still online."""
    listing = _listing(db, listing_id)
    state = leboncoin.check_ad_status(leboncoin.make_session(), listing.url or "")
    listing.last_checked_at = _now()
    if state == "gone":
        listing.is_active, listing.gone_at = False, listing.gone_at or _now()
    elif state == "active":
        listing.is_active, listing.gone_at = True, None
    freshness.apply(listing)
    db.commit()
    return {"state": state, "freshness_score": listing.freshness_score}


# ---------------------------------------------------------------- price book
class ManualPrice(BaseModel):
    median_dzd: float
    low_dzd: Optional[float] = None
    high_dzd: Optional[float] = None


def _row(row: DzPrice) -> dict:
    return {
        "id": row.id, "key": row.cache_key, "query": row.query, "kind": row.kind, "manual": bool(row.manual), "ok": bool(row.ok),
        "low_dzd": row.low_dzd, "median_dzd": row.median_dzd, "high_dzd": row.high_dzd, "confidence": row.confidence,
        "note": row.note, "sources": row.sources or [], "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


@router.get("/price-book")
def price_book(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(DzPrice).order_by(DzPrice.manual.desc(), DzPrice.fetched_at.desc())).scalars().all()
    return [_row(r) for r in rows]


@router.put("/price-book/{row_id}")
def edit_price(row_id: int, payload: ManualPrice, db: Session = Depends(get_db)) -> dict:
    row = db.get(DzPrice, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Price not found")
    row.median_dzd = round(payload.median_dzd)
    row.low_dzd = round(payload.low_dzd) if payload.low_dzd else round(row.median_dzd * 0.9)
    row.high_dzd = round(payload.high_dzd) if payload.high_dzd else round(row.median_dzd * 1.1)
    row.manual, row.ok, row.confidence, row.note = True, True, "high", "Entered manually"
    db.commit()
    return _row(row)


@router.delete("/price-book/{row_id}")
def delete_price(row_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(DzPrice, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Price not found")
    db.delete(row)
    db.commit()
    return {"deleted": row_id}


@router.put("/listings/{listing_id}/dz-price")
def set_manual_price(listing_id: int, payload: ManualPrice, db: Session = Depends(get_db)) -> dict:
    """Your own Algerian price for this product type; it overrides Gemini for every similar ad."""
    settings = get_settings(db)
    listing = _listing(db, listing_id)
    try:
        dz_market.set_manual(db, listing, payload.median_dzd, payload.low_dzd, payload.high_dzd)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    analyze.apply_dz_comparison(db, settings, listing)
    db.commit()
    return {"ok": True, "dz_price_median_dzd": listing.dz_price_median_dzd, "dz_saving_pct": listing.dz_saving_pct}
