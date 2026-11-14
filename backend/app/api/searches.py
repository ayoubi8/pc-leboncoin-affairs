from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..logistics import landed
from ..models import Listing, Run, Search, SearchListing
from ..schemas import (
    ListingCard,
    QueryPreview,
    ResultsResponse,
    RunOut,
    SearchCreate,
    SearchOut,
    SearchUpdate,
)
from ..search.query_generator import generate_queries
from ..search.runner import run_search
from ..scraping.leboncoin import build_url
from .helpers import get_settings, listing_card, run_out, search_out

router = APIRouter(prefix="/api/searches", tags=["searches"])

SORT_KEYS = {
    "best_deal": "Best deal",
    "price_asc": "Lowest price",
    "price_desc": "Highest price",
    "ram_desc": "Most RAM",
    "match_desc": "Best hardware match",
    "acquisition_desc": "Best acquisition",
    "newest": "Newest",
    "landed_asc": "Lowest landed cost",
}


def _get_search(db: Session, search_id: int) -> Search:
    search = db.get(Search, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")
    return search


@router.get("", response_model=list[SearchOut])
def list_searches(db: Session = Depends(get_db)) -> list[SearchOut]:
    searches = db.execute(select(Search).order_by(Search.created_at.desc())).scalars().all()
    return [search_out(db, search) for search in searches]


@router.post("", response_model=SearchOut, status_code=201)
def create_search(payload: SearchCreate, db: Session = Depends(get_db)) -> SearchOut:
    search = Search(**payload.model_dump())
    db.add(search)
    db.commit()
    db.refresh(search)
    return search_out(db, search)


@router.get("/{search_id}", response_model=SearchOut)
def read_search(search_id: int, db: Session = Depends(get_db)) -> SearchOut:
    return search_out(db, _get_search(db, search_id))


@router.patch("/{search_id}", response_model=SearchOut)
def update_search(search_id: int, payload: SearchUpdate, db: Session = Depends(get_db)) -> SearchOut:
    search = _get_search(db, search_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(search, field, value)
    db.commit()
    db.refresh(search)
    return search_out(db, search)


@router.delete("/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db)) -> Response:
    search = _get_search(db, search_id)
    db.delete(search)
    db.commit()
    return Response(status_code=204)


@router.post("/{search_id}/run", response_model=RunOut)
def trigger_run(
    search_id: int,
    pages: int = Query(3, ge=1, le=10),
    delay: float = Query(1.5, ge=0, le=30),
    db: Session = Depends(get_db),
) -> dict:
    search = _get_search(db, search_id)
    run = run_search(db, search.id, trigger="manual", pages=pages, delay=delay)
    return run_out(db, run, search.name)


@router.get("/{search_id}/runs", response_model=list[RunOut])
def list_runs(search_id: int, db: Session = Depends(get_db)) -> list[dict]:
    search = _get_search(db, search_id)
    runs = db.execute(
        select(Run).where(Run.search_id == search_id).order_by(Run.started_at.desc()).limit(50)
    ).scalars().all()
    return [run_out(db, run, search.name) for run in runs]


def _latest_run_id(db: Session, search_id: int) -> Optional[int]:
    return db.execute(
        select(Run.id).where(Run.search_id == search_id).order_by(Run.id.desc()).limit(1)
    ).scalar_one_or_none()


@router.get("/{search_id}/results", response_model=ResultsResponse)
def search_results(
    search_id: int,
    sort: str = Query("best_deal"),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_ram: Optional[int] = None,
    min_storage: Optional[int] = None,
    brand: str = "",
    condition: str = "",
    city: str = "",
    screen_min: Optional[float] = None,
    screen_max: Optional[float] = None,
    hide_missing_specs: bool = False,
    db: Session = Depends(get_db),
) -> ResultsResponse:
    search = _get_search(db, search_id)
    latest_run = _latest_run_id(db, search.id)

    rows = db.execute(
        select(SearchListing, Listing)
        .join(Listing, Listing.id == SearchListing.listing_id)
        .where(SearchListing.search_id == search.id)
    ).all()

    cards: list[ListingCard] = []
    listing_by_id: dict[int, Listing] = {}
    for link, listing in rows:
        specs = listing.specs or {}
        if min_price is not None and (listing.price_eur is None or listing.price_eur < min_price):
            continue
        if max_price is not None and (listing.price_eur is None or listing.price_eur > max_price):
            continue
        if min_ram is not None and (specs.get("ram_gb") or 0) < min_ram:
            continue
        if min_storage is not None and (specs.get("storage_gb") or 0) < min_storage:
            continue
        if brand and brand.lower() not in str(specs.get("brand") or listing.brand or "").lower():
            continue
        if condition and condition.lower() not in str(specs.get("condition") or listing.condition or "").lower():
            continue
        if city and city.lower() not in (listing.city or "").lower():
            continue
        if screen_min is not None and (specs.get("screen_inches") or 0) < screen_min:
            continue
        if screen_max is not None and (specs.get("screen_inches") or 0) > screen_max:
            continue
        if hide_missing_specs and not specs.get("cpu"):
            continue
        is_new = bool(latest_run and link.run_id == latest_run)
        cards.append(listing_card(listing, found_at=link.found_at, is_new=is_new))
        listing_by_id[listing.id] = listing

    landed_totals: dict[int, float] = {}
    if sort == "landed_asc":
        settings = get_settings(db)
        for card in cards:
            listing = listing_by_id.get(card.id)
            if listing is None or not listing.price_eur:
                continue
            specs = listing.specs or {}
            kind = "gpu" if specs.get("gpu") and not specs.get("cpu") and not specs.get("ram_gb") else "laptop"
            landed_totals[card.id] = landed.compute(settings, listing.price_eur, kind=kind)["total_eur"]

    def sort_key(card: ListingCard):
        if sort == "price_asc":
            return (card.price_eur is None, card.price_eur or 0)
        if sort == "price_desc":
            return (card.price_eur is None, -(card.price_eur or 0))
        if sort == "ram_desc":
            return (card.specs.get("ram_gb") is None, -(card.specs.get("ram_gb") or 0))
        if sort == "match_desc":
            return (card.match_score is None, -(card.match_score or 0))
        if sort == "acquisition_desc":
            return (card.acquisition_score is None, -(card.acquisition_score or 0))
        if sort == "newest":
            return (card.found_at is None, -(card.found_at.timestamp() if card.found_at else 0))
        if sort == "landed_asc":
            total = landed_totals.get(card.id)
            return (total is None, total or 0)
        return (card.deal_score is None, -(card.deal_score or 0), card.price_eur or 0)

    cards.sort(key=sort_key)

    return ResultsResponse(
        search_id=search.id,
        search_name=search.name,
        total=len(cards),
        returned=len(cards),
        sort=sort,
        items=cards,
    )


@router.get("/{search_id}/preview-queries", response_model=QueryPreview)
def preview_queries(search_id: int, db: Session = Depends(get_db)) -> QueryPreview:
    search = _get_search(db, search_id)
    queries = generate_queries(search)
    return QueryPreview(
        queries=[query.text for query in queries],
        leboncoin_urls=[
            build_url(
                query.text,
                1,
                query.params.get("category", ""),
                query.params.get("price_min"),
                query.params.get("price_max"),
            )
            for query in queries
        ],
    )


@router.get("/{search_id}/export.csv")
def export_csv(search_id: int, db: Session = Depends(get_db)) -> Response:
    search = _get_search(db, search_id)
    rows = db.execute(
        select(SearchListing, Listing)
        .join(Listing, Listing.id == SearchListing.listing_id)
        .where(SearchListing.search_id == search.id)
        .order_by(Listing.deal_score.desc())
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "subject", "price_eur", "city", "brand", "condition", "cpu", "cpu_family",
        "ram_gb", "storage_gb", "gpu", "screen_inches", "deal_score", "deal_label",
        "match_score", "acquisition_score", "market_median_eur", "url", "found_at",
    ])
    for link, listing in rows:
        specs = listing.specs or {}
        writer.writerow([
            listing.subject,
            listing.price_eur,
            listing.city,
            specs.get("brand") or listing.brand,
            specs.get("condition") or listing.condition,
            specs.get("cpu"),
            specs.get("cpu_family"),
            specs.get("ram_gb"),
            specs.get("storage_gb"),
            specs.get("gpu"),
            specs.get("screen_inches"),
            listing.deal_score,
            listing.deal_label,
            listing.match_score,
            listing.acquisition_score,
            listing.market_median_eur,
            listing.url,
            link.found_at.isoformat() if link.found_at else "",
        ])

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", search.name).strip("-") or f"search-{search.id}"
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}.csv"'},
    )
