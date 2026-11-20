from __future__ import annotations

import uuid
from datetime import datetime

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..intelligence import deal, dz_market, market, negotiation, verdict
from ..intelligence.analyze import apply_dz_comparison
from ..logistics import landed
from ..models import Listing, Negotiation, PriceSnapshot
from ..schemas import (
    BulkNegotiationRequest,
    ListingCard,
    ListingDetail,
    NegotiationOut,
    NegotiationRequest,
    PricePoint,
    QuoteRequest,
    QuoteResponse,
)
from .helpers import get_settings, listing_card

router = APIRouter(prefix="/api", tags=["listings"])


def _get_listing(db: Session, listing_id: int) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


def _kind(listing: Listing) -> str:
    specs = listing.specs or {}
    if specs.get("gpu") and not specs.get("cpu") and not specs.get("ram_gb"):
        return "gpu"
    return "laptop"


@router.get("/listings/{listing_id}", response_model=ListingDetail)
def read_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingDetail:
    listing = _get_listing(db, listing_id)
    settings = get_settings(db)

    snapshots = db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.listing_id == listing.id)
        .order_by(PriceSnapshot.observed_at.asc())
    ).scalars().all()

    market_info = market.compute_market(db, listing)
    cost = landed.compute(settings, listing.price_eur or 0, kind=_kind(listing), specs=listing.specs)
    recs = negotiation.recommendations(
        listing.price_eur, listing.market_median_eur, listing.deal_label
    )

    detail = ListingDetail.model_validate(listing)
    detail.price_history = [
        PricePoint(observed_at=snapshot.observed_at, price_eur=snapshot.price_eur)
        for snapshot in snapshots
    ]
    detail.market_explanation = market_info["explanation"]
    detail.negotiation = recs
    detail.landed_cost = cost
    if listing.dz_price_median_dzd is None:
        detail.dz_error = dz_market.last_error(db, listing)
    return detail


@router.post("/listings/{listing_id}/dz-price", response_model=ListingDetail)
def refresh_dz_price(listing_id: int, db: Session = Depends(get_db)) -> ListingDetail:
    """Force a fresh Gemini lookup of the Algerian price and re-score this listing."""
    listing = _get_listing(db, listing_id)
    settings = get_settings(db)
    if not dz_market.available(settings):
        raise HTTPException(status_code=400, detail="Add your OpenRouter API key in Settings first (or set OPENROUTER_API_KEY in backend/.env).")
    apply_dz_comparison(db, settings, listing, force=True)
    db.commit()
    return read_listing(listing_id, db)


class VerdictRequest(BaseModel):
    buy_price_eur: Optional[float] = None  # negotiated price; default = negotiation target


@router.post("/listings/{listing_id}/verdict", response_model=ListingDetail)
def generate_verdict(
    listing_id: int,
    payload: VerdictRequest = VerdictRequest(),
    db: Session = Depends(get_db),
) -> ListingDetail:
    """Honest resale verdict (Claude Haiku) from the Algerian price and all landed costs."""
    listing = _get_listing(db, listing_id)
    settings = get_settings(db)
    if not dz_market.available(settings):
        raise HTTPException(status_code=400, detail="Add your OpenRouter API key in Settings first (or set OPENROUTER_API_KEY in backend/.env).")
    try:
        verdict.apply(db, settings, listing, payload.buy_price_eur)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return read_listing(listing_id, db)


@router.get("/deals/best", response_model=list[ListingCard])
def best_deals(limit: int = 30, db: Session = Depends(get_db)) -> list[ListingCard]:
    """Listings with an AI verdict that are still online, ranked by profit weighted by freshness."""
    rows = db.execute(
        select(Listing)
        .where(Listing.ai_verdict_label.in_(["great", "good", "fair"]))
        .where(Listing.gone_at.is_(None), Listing.is_active.isnot(False), Listing.screen_skip == "")
        .order_by(Listing.ai_profit_eur.desc())
        .limit(300)
    ).scalars().all()
    rows.sort(key=lambda r: -((r.ai_profit_eur or 0) * (0.5 + (r.freshness_score if r.freshness_score is not None else 50) / 200)))
    return [listing_card(row) for row in rows[: min(max(limit, 1), 100)]]


@router.post("/listings/{listing_id}/quote", response_model=QuoteResponse)
def quote(listing_id: int, payload: QuoteRequest, db: Session = Depends(get_db)) -> QuoteResponse:
    listing = _get_listing(db, listing_id)
    settings = get_settings(db)

    offer = payload.offer_price_eur or listing.price_eur or 0
    score = deal.score_from_ratio(offer, listing.market_median_eur)
    label = deal.classify(score)

    kind = payload.kind if payload.kind != "custom" else _kind(listing)
    cost = landed.compute(
        settings,
        offer,
        kind=kind,
        weight_kg=payload.weight_kg,
        dims_cm=payload.package_cm,
        specs=listing.specs,
    )
    recs = negotiation.recommendations(offer, listing.market_median_eur, label)
    market_info = market.compute_market(db, listing)

    return QuoteResponse(
        offer_price_eur=round(offer, 2),
        deal_score=score,
        deal_label=label,
        saving_vs_ask_eur=deal.savings(offer, listing.price_eur),
        landed_cost=cost,
        market={
            "low_eur": market_info["low_eur"],
            "median_eur": market_info["median_eur"],
            "high_eur": market_info["high_eur"],
            "confidence": market_info["confidence"],
            "samples": market_info["samples"],
            "explanation": market_info["explanation"],
        },
        negotiation=recs,
    )


@router.post("/listings/{listing_id}/negotiation", response_model=NegotiationOut)
def create_negotiation(
    listing_id: int,
    payload: NegotiationRequest,
    db: Session = Depends(get_db),
) -> Negotiation:
    listing = _get_listing(db, listing_id)
    settings = get_settings(db)

    result = negotiation.build(
        db,
        settings,
        listing,
        tone=payload.tone,
        offer_override=payload.offer_price_eur,
        custom_note=payload.custom_note,
    )
    row = Negotiation(
        listing_id=listing.id,
        tone=result["tone"],
        ask_price_eur=result["ask_price_eur"],
        offer_price_eur=result["offer_price_eur"],
        target_price_eur=result["target_price_eur"],
        max_price_eur=result["max_price_eur"],
        message_fr=result["message_fr"],
        model=result["model"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/negotiations/bulk", response_model=list[NegotiationOut])
def bulk_negotiation(
    payload: BulkNegotiationRequest,
    db: Session = Depends(get_db),
) -> list[Negotiation]:
    settings = get_settings(db)
    batch_id = uuid.uuid4().hex[:16]
    rows: list[Negotiation] = []

    for listing_id in payload.listing_ids:
        listing = db.get(Listing, listing_id)
        if listing is None:
            continue
        result = negotiation.build(db, settings, listing, tone=payload.tone)
        row = Negotiation(
            listing_id=listing.id,
            batch_id=batch_id,
            tone=result["tone"],
            ask_price_eur=result["ask_price_eur"],
            offer_price_eur=result["offer_price_eur"],
            target_price_eur=result["target_price_eur"],
            max_price_eur=result["max_price_eur"],
            message_fr=result["message_fr"],
            model=result["model"],
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
