from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from .db import SessionLocal
from .models import Search
from .search.runner import run_search

scheduler = BackgroundScheduler(timezone="UTC")
_lock = threading.Lock()

INTERVAL_HOURS = {"6h": 6, "daily": 24, "weekly": 168}


def check_due_searches() -> None:
    if not _lock.acquire(blocking=False):
        return
    try:
        with SessionLocal() as db:
            from .api.helpers import get_settings

            settings = get_settings(db)
            if not settings.auto_check_enabled:
                return
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            searches = db.execute(
                select(Search).where(Search.auto_check_enabled.is_(True))
            ).scalars().all()
            for search in searches:
                hours = INTERVAL_HOURS.get(search.interval, 24)
                if search.last_run_at and now - search.last_run_at < timedelta(hours=hours):
                    continue
                try:
                    run_search(db, search.id, trigger="auto")
                except Exception as exc:  # keep the scheduler alive
                    search.last_run_status = "failed"
                    search.last_run_at = now
                    db.commit()
                    print(f"[scheduler] search {search.id} failed: {exc}")
    finally:
        _lock.release()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        check_due_searches,
        "interval",
        minutes=15,
        id="auto_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
