"""Health, deal pipeline, price book and availability endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import progress
from ..db import get_db
from ..intelligence import analyze, dz_market, freshness
from ..models import DzPrice, Listing, Run, Search
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


# ---------------------------------------------------------------- live status
@router.get("/live")
def live(db: Session = Depends(get_db)) -> dict:
    """Everything the 'Backend live' panel needs, cheap enough to poll every few seconds."""
    import time

    from ..config import SERVERLESS
    from ..scheduler import INTERVAL_MINUTES, TICK_MINUTES

    settings = get_settings(db)
    now = _now()
    searches = db.execute(select(Search).where(Search.auto_check_enabled.is_(True))).scalars().all()

    upcoming = []
    for search in searches:
        minutes = INTERVAL_MINUTES.get(search.interval, 24 * 60)
        due = (search.last_run_at + timedelta(minutes=minutes)) if search.last_run_at else now
        upcoming.append({"search_id": search.id, "name": search.name, "due_in_s": max(0, int((due - now).total_seconds()))})
    upcoming.sort(key=lambda item: item["due_in_s"])

    running = progress.running()
    busy_ids = {r["search_id"] for r in running}
    last = db.execute(select(Run).order_by(Run.id.desc()).limit(1)).scalar_one_or_none()

    tick = progress.last_tick("scan_tick")
    poll = progress.last_tick("telegram_poll")
    health = system.compute_health(db, settings)
    return {
        "now": now.isoformat(),
        "scheduler": "cron" if SERVERLESS else ("running" if tick else "starting"),
        "uptime_s": progress.uptime_seconds(),
        "tick_every_s": TICK_MINUTES * 60,
        "last_tick_s_ago": round(time.time() - tick) if tick else None,
        "auto_enabled": bool(settings.auto_check_enabled),
        "running": running,
        "next": next((u for u in upcoming if u["search_id"] not in busy_ids), None),
        "upcoming": upcoming[:6],
        "last_run": {
            "id": last.id, "search_id": last.search_id, "status": last.status,
            "new_count": last.new_count, "results_total": last.results_total,
            "finished_at": last.finished_at.isoformat() if last.finished_at else None,
        } if last else None,
        "telegram": {
            "enabled": bool(settings.telegram_enabled),
            "linked": bool((settings.telegram_chat_id or "").strip()),
            "last_poll_s_ago": round(time.time() - poll) if poll else None,
        },
        "openrouter": health["openrouter_key"],
        "ok": health["ok"],
        "problems": health["problems"],
        "events": progress.events(25),
    }


# ---------------------------------------------------------------- act now
@router.get("/deals/act-now")
def act_now(limit: int = 6, db: Session = Depends(get_db)) -> dict:
    """Fresh, still-online, profitable ads you have not acted on yet, best first."""
    from ..intelligence import freshness

    settings = get_settings(db)
    max_age = float(settings.max_ad_age_hours or 48)
    query = (
        select(Listing)
        .where(Listing.gone_at.is_(None), Listing.is_active.is_not(False))
        .where((Listing.screen_skip.is_(None)) | (Listing.screen_skip == ""))
        .where((Listing.pipeline_status.is_(None)) | (Listing.pipeline_status.in_(["", "new"])))
        .order_by(Listing.id.desc())
        .limit(600)
    )
    if not settings.alert_pickup_only:  # pickup-only ads cannot go to the forwarder
        query = query.where((Listing.ship_ok.is_(None)) | (Listing.ship_ok != "no"))
    rows = db.execute(query).scalars().all()

    scored, unpriced = [], 0
    for listing in rows:
        age = freshness.age_hours(listing)
        if age is None or age > max_age:
            continue
        profit = listing.profit_ask_eur if listing.profit_ask_eur is not None else listing.ai_profit_eur
        if profit is None:
            unpriced += 1
            continue
        if profit <= 0:
            continue
        rank = profit * (0.5 + (listing.freshness_score or 50) / 200)
        scored.append((rank, listing))
    scored.sort(key=lambda item: -item[0])
    return {
        "items": [listing_card(listing) for _, listing in scored[: max(1, min(limit, 20))]],
        "unpriced_fresh": unpriced,
        "max_age_hours": max_age,
    }
