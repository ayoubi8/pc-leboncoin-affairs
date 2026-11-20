from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Listing, Search, Settings
from app.extraction import llm
from app.scraping import leboncoin
from app.search import runner


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add(Settings(id=1, dz_price_enabled=False))
    db.add(Search(name="s", interval="10m"))
    db.commit()
    return db


def _raw(i, subject="Laptop i5 16Go", seller="u1", price=300, **extra):
    return {"list_id": i, "subject": subject, "price": [price], "first_publication_date": "2026-11-20 10:00:00",
            "index_date": "2026-11-20 10:00:00", "url": f"/ad/{i}", "owner": {"user_id": seller, "type": "private"},
            "location": {"city": "Paris"}, "attributes": [], "images": {}, **extra}


def _patch(monkeypatch, pages):
    calls = []

    def fake_fetch(session, text, page=1, **kw):
        calls.append(page)
        return leboncoin.ScrapePage(ads=pages.get(page, []))

    monkeypatch.setattr(leboncoin, "fetch_page", fake_fetch)
    monkeypatch.setattr(leboncoin, "make_session", lambda: None)
    monkeypatch.setattr(llm, "available", lambda s: False)  # no network in tests
    monkeypatch.setattr(runner.time, "sleep", lambda *_: None)
    return calls


def test_stops_paging_when_page_is_already_known(monkeypatch):
    db = _db()
    calls = _patch(monkeypatch, {1: [_raw(i) for i in range(1, 6)], 2: [_raw(i) for i in range(6, 11)], 3: [_raw(11)]})
    runner.run_search(db, 1, pages=3)
    assert calls.count(3) >= 1  # first run: nothing known yet, walks all pages (per query)

    calls.clear()
    _patch(monkeypatch, {1: [_raw(i) for i in range(1, 6)], 2: [_raw(99)]})  # same page-1 ads again
    calls = _patch(monkeypatch, {1: [_raw(i) for i in range(1, 6)], 2: [_raw(99)]})
    runner.run_search(db, 1, pages=3)
    assert 2 not in calls  # page 1 was fully known -> never asked for page 2


def test_repost_is_linked_and_not_alerted_twice(monkeypatch):
    db = _db()
    _patch(monkeypatch, {1: [_raw(1, subject="MacBook Air M1", seller="seller9")]})
    runner.run_search(db, 1, pages=1)
    first = db.query(Listing).filter(Listing.list_id == "1").one()
    first.notified_at = datetime(2026, 11, 20, 12, 0)
    db.commit()

    _patch(monkeypatch, {1: [_raw(2, subject="MacBook  Air M1", seller="seller9", price=280)]})
    runner.run_search(db, 1, pages=1)
    repost = db.query(Listing).filter(Listing.list_id == "2").one()
    assert repost.repost_of_id == first.id
    assert repost.notified_at == first.notified_at  # already alerted via the original
    db.refresh(first)
    assert first.repost_count == 1


def test_sold_and_broken_ads_skip_the_paid_lookup(monkeypatch):
    db = _db()
    settings = db.get(Settings, 1)
    settings.dz_price_enabled = True
    settings.llm_api_key = "k"
    db.commit()
    from app.intelligence import dz_market

    called = []
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: called.append(1) or {"ok": False, "error": "x"})
    sold = _raw(1, attributes=[{"key": "transaction_status", "value": "sold"}])
    broken = _raw(2, subject="Dell XPS pour pièces")
    _patch(monkeypatch, {1: [sold, broken]})
    runner.run_search(db, 1, pages=1)
    assert called == []
    a = db.query(Listing).filter(Listing.list_id == "1").one()
    assert a.is_active is False and a.gone_at is not None and a.screen_skip
    assert db.query(Listing).filter(Listing.list_id == "2").one().screen_skip


def test_hard_filters_and_gpu_queries():
    from app.intelligence import match
    from app.search import query_generator

    search = Search(name="x", cpu="i5-13420h", ram_min=16, include_missing_specs=True)
    ok = Listing(subject="a", specs={"cpu": "i5-13420h", "ram_gb": 16})
    wrong_cpu = Listing(subject="b", specs={"cpu": "i3-1115g4", "ram_gb": 16})
    low_ram = Listing(subject="c", specs={"cpu": "i5-13420h", "ram_gb": 8})
    unknown = Listing(subject="d", specs={})
    assert match.hard_fail(search, ok) == "" and match.hard_fail(search, wrong_cpu) and match.hard_fail(search, low_ram)
    assert match.hard_fail(search, unknown) == ""  # missing specs allowed
    search.include_missing_specs = False
    assert match.hard_fail(search, unknown)

    gpu = Search(name="g", kind="gpu", gpu="RTX 3060", price_max=300)
    queries = query_generator.generate_queries(gpu)
    assert [q.text for q in queries] == ["RTX 3060", "carte graphique RTX 3060"]
    assert all(q.params["category"] == "83" and q.params["price_max"] == 300 for q in queries)
