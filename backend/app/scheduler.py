from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from . import progress
from .db import SessionLocal
from .models import Listing, Search
from .notify import poller, system
from .search.runner import run_search

scheduler = None  # created in start_scheduler (apscheduler is not installed on serverless)
_lock = threading.Lock()

INTERVAL_HOURS = {"1h": 1, "6h": 6, "12h": 12, "daily": 24, "weekly": 168}
INTERVAL_MINUTES = {"10m": 10, "15m": 15, "30m": 30, **{k: v * 60 for k, v in INTERVAL_HOURS.items()}}
TICK_MINUTES = 2  # how often due searches are looked for (short, so a 10-minute interval stays ~10 minutes)


SEARCH_GAP_SECONDS = (20, 40)  # pause between searches due together, so the reader does not rate limit us
RECHECK_EVERY = timedelta(hours=6)
RECHECK_PER_TICK = 5


def recheck_watchlist(db, now: datetime) -> int:
    """Re-verify ads we already alerted about (or you acted on) so dead ads drop out of the lists."""
    from .scraping import leboncoin

    due = db.execute(
        select(Listing)
        .where(Listing.notified_at.is_not(None), Listing.gone_at.is_(None))
        .where(Listing.pipeline_status.notin_(["bought", "shipped", "sold", "skipped"]))
        .where((Listing.last_checked_at.is_(None)) | (Listing.last_checked_at < now - RECHECK_EVERY))
        .order_by(Listing.last_checked_at.asc())
        .limit(RECHECK_PER_TICK)
    ).scalars().all()
    if not due:
        return 0
    session = leboncoin.make_session()
    for listing in due:
        state = leboncoin.check_ad_status(session, listing.url or "")
        listing.last_checked_at = now
        if state == "gone":
            listing.is_active, listing.gone_at, listing.freshness_score = False, now, 0.0
    db.commit()
    return len(due)


def housekeeping(db, settings, now: datetime) -> None:
    """Cheap upkeep done on every tick; never raises."""
    for name, func in (
        ("system alerts", lambda: system.check_and_alert(db, settings)),
        ("availability re-check", lambda: recheck_watchlist(db, now)),
        # the long-polling thread reads Telegram when it runs; two readers at once would make Telegram refuse both
        ("telegram updates", lambda: None if polling() else poller.process_updates(db, settings)),
    ):
        try:
            func()
        except Exception as exc:
            db.rollback()
            print(f"[scheduler] {name} failed: {type(exc).__name__}: {exc}")


LONG_POLL_SECONDS = 25
_poll_thread: threading.Thread | None = None
_stop_polling = threading.Event()


def polling() -> bool:
    return _poll_thread is not None and _poll_thread.is_alive()


def poll_telegram(wait: int = 0) -> int:
    """Button presses and commands. With ``wait``, Telegram holds the request until something arrives."""
    progress.tick("telegram_poll")
    try:
        with SessionLocal() as db:
            from .api.helpers import get_settings

            return poller.process_updates(db, get_settings(db), wait)
    except Exception as exc:
        print(f"[telegram] poll failed: {type(exc).__name__}: {exc}")
        return -1


def _poll_forever() -> None:
    """Long polling: a tap is handled as soon as Telegram receives it, and a slow reply never skips a poll."""
    from .api.helpers import get_settings
    from .notify import telegram

    menu_set_for = ""
    while not _stop_polling.is_set():
        try:
            with SessionLocal() as db:
                settings = get_settings(db)
                ready = poller.ready(settings)
                token = settings.telegram_bot_token or ""
            if not ready:
                _stop_polling.wait(10)
                continue
            if menu_set_for != token and telegram.set_commands(token)["ok"]:
                menu_set_for = token  # commands appear in Telegram's / menu
            started = time.monotonic()
            if poll_telegram(LONG_POLL_SECONDS) <= 0 and time.monotonic() - started < 2:
                _stop_polling.wait(3)  # Telegram refused or the network is down: do not spin
        except Exception as exc:  # the thread must never die
            print(f"[telegram] poll loop: {type(exc).__name__}: {exc}")
            _stop_polling.wait(5)


def check_due_searches(budget_seconds: float | None = None) -> dict:
    """Run every search that is due. With a budget, stop starting new ones once it is spent
    (the rest stay due and are picked up by the next tick)."""
    result = {"ran": [], "skipped_for_budget": 0, "busy": False}
    if not _lock.acquire(blocking=False):
        result["busy"] = True
        return result
    started = time.monotonic()
    progress.tick("scan_tick")
    try:
        with SessionLocal() as db:
            from .api.helpers import get_settings

            settings = get_settings(db)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            housekeeping(db, settings, now)
            if not settings.auto_check_enabled:
                return result
            searches = db.execute(
                select(Search).where(Search.auto_check_enabled.is_(True))
            ).scalars().all()
            busy = {run["search_id"] for run in progress.running()}
            finished = []
            for search in searches:
                minutes = INTERVAL_MINUTES.get(search.interval, 24 * 60)
                if search.id in busy:  # a manual scan of it is already running
                    continue
                if search.last_run_at and now - search.last_run_at < timedelta(minutes=minutes - TICK_MINUTES):
                    continue
                if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                    result["skipped_for_budget"] += 1
                    continue
                if result["ran"] and budget_seconds is None:
                    time.sleep(random.uniform(*SEARCH_GAP_SECONDS))
                result["ran"].append(search.id)
                # Claim the slot first: if a serverless timeout kills this run, the search is
                # not retried on every tick, only when its interval comes round again.
                search.last_run_at = now
                db.commit()
                try:
                    finished.append(run_search(db, search.id, trigger="auto"))
                except Exception as exc:  # keep the scheduler alive
                    search.last_run_status = "failed"
                    search.last_run_at = now
                    db.commit()
                    print(f"[scheduler] search {search.id} failed: {exc}")
            if result["ran"]:
                try:
                    from .notify import deals

                    deals.send_round_digest(db, settings, len(result["ran"]), finished)
                except Exception as exc:  # a digest must never stop the scheduler
                    print(f"[scheduler] digest failed: {type(exc).__name__}: {exc}")
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
    global _poll_thread
    if not polling():
        _stop_polling.clear()
        _poll_thread = threading.Thread(target=_poll_forever, daemon=True, name="telegram-poll")
        _poll_thread.start()


def stop_scheduler() -> None:
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
    _stop_polling.set()
