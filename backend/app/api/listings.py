from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..intelligence import deal, market, negotiation
from ..logistics import landed
from ..models import Listing, Negotiation, PriceSnapshot
from ..schemas import (
    BulkNegotiationRequest,
    ListingDetail,
    NegotiationOut,
    NegotiationRequest,
    PricePoint,
    QuoteRequest,
    QuoteResponse,
)
from .helpers import get_settings

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
    cost = landed.compute(settings, listing.price_eur or 0, kind=_kind(listing))
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
    return detail


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
