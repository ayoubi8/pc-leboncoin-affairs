from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Listing, PriceSnapshot, Run, Search
from ..schemas import DashboardKPIs, DashboardOut
from .helpers import get_settings, listing_card, run_out

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)) -> DashboardOut:
    get_settings(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    searches = db.execute(select(Search)).scalars().all()
    active_searches = sum(1 for s in searches if s.auto_check_enabled or s.last_run_at is not None)

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = db.execute(
        select(func.count(Listing.id)).where(Listing.first_seen_at >= day_start)
    ).scalar_one()

    total_listings = db.execute(select(func.count(Listing.id))).scalar_one()

    best = db.execute(
        select(Listing)
        .where(Listing.deal_score.is_not(None))
        .order_by(Listing.deal_score.desc(), Listing.price_eur.asc())
        .limit(1)
    ).scalar_one_or_none()

    best_deal = None
    if best:
        card = listing_card(best)
        best_deal = {
            "id": card.id,
            "subject": card.subject,
            "price_eur": card.price_eur,
            "deal_score": card.deal_score,
            "deal_label": card.deal_label,
            "market_median_eur": card.market_median_eur,
            "url": card.url,
        }

    runs = db.execute(select(Run).order_by(Run.started_at.desc()).limit(5)).scalars().all()
    search_names = {s.id: s.name for s in searches}
    recent_runs = [run_out(db, run, search_names.get(run.search_id)) for run in runs]

    top = db.execute(
        select(Listing)
        .where(Listing.deal_score.is_not(None))
        .order_by(Listing.deal_score.desc(), Listing.price_eur.asc())
        .limit(5)
    ).scalars().all()
    best_deals = [listing_card(listing) for listing in top]

    alerts: list[dict] = []

    snapshots = db.execute(
        select(PriceSnapshot).order_by(PriceSnapshot.observed_at.desc()).limit(800)
    ).scalars().all()
    by_listing: dict[int, list[PriceSnapshot]] = {}
    for snapshot in snapshots:
        by_listing.setdefault(snapshot.listing_id, []).append(snapshot)
    for listing_id, items in by_listing.items():
        if len(items) < 2:
            continue
        latest, previous = items[0], items[1]
        if latest.price_eur and previous.price_eur and latest.price_eur < previous.price_eur - 1:
            listing = db.get(Listing, listing_id)
            if listing:
                alerts.append(
                    {
                        "type": "price_drop",
                        "listing_id": listing.id,
                        "subject": listing.subject,
                        "old_eur": previous.price_eur,
                        "new_eur": latest.price_eur,
                        "at": latest.observed_at.isoformat(),
                        "message": f"Price dropped from {previous.price_eur:.0f} € to {latest.price_eur:.0f} €",
                    }
                )

    failed = db.execute(
        select(Run)
        .where(Run.status.in_(["failed", "blocked"]))
        .where(Run.started_at >= now - timedelta(days=14))
        .order_by(Run.started_at.desc())
        .limit(5)
    ).scalars().all()
    for run in failed:
        alerts.append(
            {
                "type": "check_failed",
                "run_id": run.id,
                "search_id": run.search_id,
                "search_name": search_names.get(run.search_id, ""),
                "status": run.status,
                "at": (run.started_at or now).isoformat(),
                "message": run.error or f"Check {run.status}",
            }
        )

    alerts.sort(key=lambda item: item.get("at") or "", reverse=True)

    return DashboardOut(
        kpis=DashboardKPIs(
            active_searches=active_searches,
            new_today=new_today,
            best_deal=best_deal,
            total_listings=total_listings,
        ),
        recent_runs=recent_runs,
        best_deals=best_deals,
        alerts=alerts[:8],
    )
