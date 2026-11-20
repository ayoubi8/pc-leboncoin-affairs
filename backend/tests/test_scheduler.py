from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.db import Base
from app.models import Search, Settings


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _setup(monkeypatch, searches, auto=True):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Settings(id=1, auto_check_enabled=auto))
        db.add_all(searches)
        db.commit()
    ran = []
    monkeypatch.setattr(scheduler, "SessionLocal", Session)
    monkeypatch.setattr(scheduler, "run_search", lambda db, sid, trigger="manual", **kw: ran.append((sid, trigger)))
    return ran


def _search(name, interval, age_minutes=None, enabled=True):
    last = None if age_minutes is None else _now() - timedelta(minutes=age_minutes)
    return Search(name=name, interval=interval, auto_check_enabled=enabled, last_run_at=last)


def test_due_searches_run_and_others_wait(monkeypatch):
    ran = _setup(monkeypatch, [
        _search("never-run", "1h", None),            # id 1: never ran -> run
        _search("1h-old", "1h", 61),                 # id 2: due
        _search("1h-fresh", "1h", 30),               # id 3: wait
        _search("6h-due", "6h", 6 * 60 + 1),         # id 4: due
        _search("6h-fresh", "6h", 5 * 60),           # id 5: wait
        _search("12h-due", "12h", 12 * 60 + 1),      # id 6: due
        _search("12h-fresh", "12h", 11 * 60),        # id 7: wait
        _search("daily-due", "daily", 24 * 60 + 1),  # id 8: due
        _search("daily-fresh", "daily", 23 * 60),    # id 9: wait
        _search("disabled", "1h", 600, enabled=False),  # id 10: never
    ])
    scheduler.check_due_searches()
    assert sorted(sid for sid, _ in ran) == [1, 2, 4, 6, 8]
    assert all(trigger == "auto" for _, trigger in ran)


def test_global_switch_off_runs_nothing(monkeypatch):
    ran = _setup(monkeypatch, [_search("a", "1h", None)], auto=False)
    scheduler.check_due_searches()
    assert ran == []


def test_cadence_stays_close_to_interval(monkeypatch):
    # A 1h search that finished 58 minutes ago must run on the next tick, not wait a full extra tick.
    ran = _setup(monkeypatch, [_search("tight", "1h", 58)])
    scheduler.check_due_searches()
    assert [sid for sid, _ in ran] == [1]
