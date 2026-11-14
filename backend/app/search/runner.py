from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..intelligence.analyze import analyze_listing
from ..models import Listing, PriceSnapshot, Run, Search, SearchListing, Settings
from ..processing.dedup import dedupe_ads, price_changed
from ..scraping import leboncoin
from .query_generator import GeneratedQuery, generate_queries


def get_settings(db: Session) -> Settings:
    settings = db.get(Settings, 1)
    if settings is None:
        settings = Settings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _find_listing(db: Session, ad: dict[str, Any]) -> Optional[Listing]:
    if ad.get("list_id"):
        found = db.execute(
            select(Listing).where(Listing.list_id == ad["list_id"])
        ).scalar_one_or_none()
        if found:
            return found
    url = (ad.get("url") or "").split("?")[0].rstrip("/")
    candidates = {value for value in (ad.get("url") or "", url) if value}
    if candidates:
        return db.execute(
            select(Listing).where(Listing.url.in_(candidates))
        ).scalars().first()
    return None


def upsert_ads(
    db: Session,
    settings: Settings,
    search: Search,
    run: Optional[Run],
    ads: list[dict[str, Any]],
) -> dict[str, Any]:
    new_listings: list[Listing] = []
    changed_listings: list[Listing] = []
    touched: list[Listing] = []

    for ad in ads:
        listing = _find_listing(db, ad)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if listing is None:
            listing = Listing(
                list_id=ad.get("list_id"),
                url=ad.get("url") or "",
                subject=ad.get("subject") or "",
                price_cents=ad.get("price_cents"),
                price_eur=ad.get("price_eur"),
                category_id=ad.get("category_id") or "",
                city=ad.get("city") or "",
                zipcode=ad.get("zipcode") or "",
                department=ad.get("department") or "",
                brand=ad.get("brand") or "",
                condition=ad.get("condition") or "",
                description=ad.get("description") or "",
                images=ad.get("images") or [],
                first_publication_date=ad.get("first_publication_date") or "",
                is_boosted=bool(ad.get("is_boosted")),
                is_pro=bool(ad.get("is_pro")),
                raw=ad.get("raw") or {},
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(listing)
            db.flush()
            new_listings.append(listing)
            db.add(PriceSnapshot(listing_id=listing.id, price_eur=listing.price_eur, run_id=run.id if run else None))
        else:
            previous = listing.price_eur
            if ad.get("price_eur") is not None:
                listing.price_eur = ad.get("price_eur")
                listing.price_cents = ad.get("price_cents") or listing.price_cents
            listing.last_seen_at = now
            if not listing.subject:
                listing.subject = ad.get("subject") or ""
            if not listing.description:
                listing.description = ad.get("description") or ""
            images = ad.get("images") or []
            if images:
                listing.images = images
            if not listing.url:
                listing.url = ad.get("url") or ""
            if price_changed(previous, listing.price_eur):
                changed_listings.append(listing)
                db.add(PriceSnapshot(listing_id=listing.id, price_eur=listing.price_eur, run_id=run.id if run else None))

        link = db.execute(
            select(SearchListing).where(
                SearchListing.search_id == search.id,
                SearchListing.listing_id == listing.id,
            )
        ).scalar_one_or_none()
        if link is None:
            db.add(SearchListing(search_id=search.id, listing_id=listing.id, run_id=run.id if run else None))
        elif run is not None:
            link.run_id = run.id

        touched.append(listing)

    db.flush()

    for listing in touched:
        is_new = listing in new_listings
        is_changed = listing in changed_listings
        if is_new or is_changed or listing.last_analyzed_at is None:
            analyze_listing(db, settings, listing, search, force=is_new)

    db.commit()

    return {
        "new": len(new_listings),
        "updated": len(changed_listings),
        "skipped": max(0, len(ads) - len(new_listings) - len(changed_listings)),
        "touched": len(touched),
    }


def run_search(
    db: Session,
    search_id: int,
    trigger: str = "manual",
    pages: int = 3,
    delay: float = 1.5,
) -> Run:
    search = db.get(Search, search_id)
    if search is None:
        raise ValueError(f"search {search_id} not found")

    settings = get_settings(db)
    run = Run(search_id=search.id, trigger=trigger, status="running", started_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(run)
    db.commit()
    db.refresh(run)

    queries: list[GeneratedQuery] = generate_queries(search)
    run.queries_total = len(queries)
    db.commit()

    ads: list[dict[str, Any]] = []
    blocked = False
    error: Optional[str] = None
    session = leboncoin.make_session()

    try:
        for index, query in enumerate(queries):
            for page in range(1, max(1, pages) + 1):
                result = leboncoin.fetch_page(
                    session,
                    query.text,
                    page=page,
                    category=query.params.get("category", ""),
                    price_min=query.params.get("price_min"),
                    price_max=query.params.get("price_max"),
                )
                if result.blocked:
                    blocked = True
                    error = result.error
                    break
                if result.error:
                    error = result.error
                    break
                if not result.ads:
                    break
                ads.extend(leboncoin.normalize_ad(raw) for raw in result.ads)
                if page < pages:
                    time.sleep(delay)
            if blocked:
                break
            if index < len(queries) - 1:
                time.sleep(delay)

        # local filters (price + loose location match)
        if search.price_min is not None:
            ads = [ad for ad in ads if ad.get("price_eur") is None or ad["price_eur"] >= search.price_min]
        if search.price_max is not None:
            ads = [ad for ad in ads if ad.get("price_eur") is None or ad["price_eur"] <= search.price_max]
        if search.location:
            needle = search.location.strip().lower()
            ads = [
                ad for ad in ads
                if not ad.get("city") or needle in (ad.get("city") or "").lower()
                or needle in (ad.get("department") or "").lower()
            ]

        unique = dedupe_ads(ads)
        run.results_total = len(unique)

        counts = upsert_ads(db, settings, search, run, unique)
        run.new_count = counts["new"]
        run.updated_count = counts["updated"]
        run.skipped_count = counts["skipped"]

        if blocked and not unique:
            run.status = "blocked"
        elif unique or not error:
            run.status = "success"
        else:
            run.status = "failed"
    except Exception as exc:  # keep the run row for the UI
        db.rollback()
        run = db.get(Run, run.id)
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        error = run.error
    finally:
        run.datadome_blocked = run.status == "blocked"
        run.error = run.error or error
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        search.last_run_at = run.finished_at
        search.last_run_status = run.status
        db.commit()

    return run
