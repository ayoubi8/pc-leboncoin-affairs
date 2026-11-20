from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import SessionLocal
from .models import Search
from .search.runner import run_search

scheduler = None  # created in start_scheduler (apscheduler is not installed on serverless)
_lock = threading.Lock()

INTERVAL_HOURS = {"1h": 1, "6h": 6, "12h": 12, "daily": 24, "weekly": 168}
TICK_MINUTES = 5  # how often due searches are looked for


def check_due_searches(budget_seconds: float | None = None) -> dict:
    """Run every search that is due. With a budget, stop starting new ones once it is spent
    (the rest stay due and are picked up by the next tick)."""
    result = {"ran": [], "skipped_for_budget": 0, "busy": False}
    if not _lock.acquire(blocking=False):
        result["busy"] = True
        return result
    started = time.monotonic()
    try:
        with SessionLocal() as db:
            from .api.helpers import get_settings

            settings = get_settings(db)
            if not settings.auto_check_enabled:
                return result
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            searches = db.execute(
                select(Search).where(Search.auto_check_enabled.is_(True))
            ).scalars().all()
            for search in searches:
                hours = INTERVAL_HOURS.get(search.interval, 24)
                if search.last_run_at and now - search.last_run_at < timedelta(hours=hours) - timedelta(minutes=TICK_MINUTES):
                    continue
                if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                    result["skipped_for_budget"] += 1
                    continue
                result["ran"].append(search.id)
                # Claim the slot first: if a serverless timeout kills this run, the search is
                # not retried on every tick, only when its interval comes round again.
                search.last_run_at = now
                db.commit()
                try:
                    run_search(db, search.id, trigger="auto")
                except Exception as exc:  # keep the scheduler alive
                    search.last_run_status = "failed"
                    search.last_run_at = now
                    db.commit()
                    print(f"[scheduler] search {search.id} failed: {exc}")
    finally:
        _lock.release()
    return result


def start_scheduler() -> None:
    global scheduler
    if scheduler is not None and scheduler.running:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        check_due_searches,
        "interval",
        minutes=TICK_MINUTES,
        id="auto_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
