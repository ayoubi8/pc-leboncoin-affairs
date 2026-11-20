from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..intelligence import freshness
from ..models import Listing, Run, Search, SearchListing, Settings
from ..schemas import ListingCard, SearchOut


def get_settings(db: Session) -> Settings:
    settings = db.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def search_result_count(db: Session, search_id: int) -> int:
    return len(
        db.execute(
            select(SearchListing.id).where(SearchListing.search_id == search_id)
        ).all()
    )


def search_out(db: Session, search: Search) -> SearchOut:
    data = SearchOut.model_validate(search)
    data.result_count = search_result_count(db, search.id)
    return data


def run_out(db: Session, run: Run, search_name: Optional[str] = None) -> dict:
    data = {
        "id": run.id,
        "search_id": run.search_id,
        "search_name": search_name,
        "trigger": run.trigger,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "queries_total": run.queries_total or 0,
        "results_total": run.results_total or 0,
        "new_count": run.new_count or 0,
        "updated_count": run.updated_count or 0,
        "skipped_count": run.skipped_count or 0,
        "datadome_blocked": bool(run.datadome_blocked),
        "error": run.error,
    }
    return data


def listing_card(listing: Listing, found_at: Optional[datetime] = None, is_new: bool = False) -> ListingCard:
    return ListingCard(
        id=listing.id,
        url=listing.url or "",
        subject=listing.subject or "",
        price_eur=listing.price_eur,
        city=listing.city or "",
        brand=(listing.specs or {}).get("brand") or listing.brand or "",
        condition=(listing.specs or {}).get("condition") or listing.condition or "",
        images=listing.images or [],
        first_publication_date=listing.first_publication_date or "",
        specs=listing.specs or {},
        spec_confidence=listing.spec_confidence or {},
        deal_score=listing.deal_score,
        deal_label=listing.deal_label,
        match_score=listing.match_score,
        acquisition_score=listing.acquisition_score,
        market_median_eur=listing.market_median_eur,
        dz_price_median_dzd=listing.dz_price_median_dzd,
        dz_landed_dzd=listing.dz_landed_dzd,
        dz_saving_pct=listing.dz_saving_pct,
        ai_verdict_label=listing.ai_verdict_label,
        ai_profit_eur=listing.ai_profit_eur,
        profit_ask_eur=listing.profit_ask_eur,
        freshness_score=listing.freshness_score,
        age_hours=freshness.age_hours(listing),
        is_active=listing.is_active is not False and listing.gone_at is None,
        ship_ok=listing.ship_ok,
        risk_flags=list(listing.risk_flags or []),
        screen_skip=listing.screen_skip or "",
        pipeline_status=listing.pipeline_status or "",
        is_new=is_new,
        found_at=found_at,
    )


def mask_key(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return f"••••{value[-4:]}"
