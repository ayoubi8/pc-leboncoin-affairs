from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import searches as searches_api
from app.db import Base, get_db
from app.intelligence import verdict
from app.models import Listing, Search, SearchListing, Settings
from app.notify import deals, telegram


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _setup(db):
    settings = Settings(id=1, telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="1", llm_api_key="k")
    search = Search(name="s", notify_telegram=True)
    db.add_all([settings, search])
    db.commit()
    return settings, search


def _listing(db, subject, dz_median, saving, price=220.0):
    listing = Listing(
        subject=subject, price_eur=price, url="https://lbc/x", first_publication_date="2026-11-14 10:00:00",
        specs={"cpu": "i5-13420h", "ram_gb": 16}, dz_price_median_dzd=dz_median, dz_price_low_dzd=dz_median * 0.9,
        dz_price_high_dzd=dz_median * 1.1, dz_confidence="medium", dz_saving_pct=saving, images=[],
    )
    db.add(listing)
    db.commit()
    return listing


def test_only_profitable_new_deals_are_sent_once(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    good = _listing(db, "Great <b>laptop</b>", 150_000, 40.0)
    bad = _listing(db, "Meh laptop", 40_000, -30.0)
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: None)  # rule-based verdicts
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda s, text, photo_url=None, buttons=None: sent.append(text) or {"ok": True})

    stats = deals.notify_run(db, settings, search, [good, bad])
    assert stats["sent"] == 1 and len(sent) == 1
    assert "&lt;b&gt;laptop&lt;/b&gt;" in sent[0]  # ad text is HTML-escaped
    assert good.notified_at is not None and bad.notified_at is None

    stats = deals.notify_run(db, settings, search, [good, bad])
    assert stats["sent"] == 0  # never alerted twice


def test_failed_send_is_retried_next_run(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    good = _listing(db, "Great laptop", 150_000, 40.0)
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: None)
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: {"ok": False, "error": "boom"})
    assert deals.notify_run(db, settings, search, [good])["sent"] == 0
    assert good.notified_at is None


def test_cap_per_run(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    settings.notify_max_per_run = 2
    db.commit()
    items = [_listing(db, f"L{i}", 150_000 + i * 1000, 40.0) for i in range(4)]
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: None)
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda s, text, photo_url=None, buttons=None: sent.append(text) or {"ok": True})
    stats = deals.notify_run(db, settings, search, items)
    assert stats["sent"] == 2
    assert len(sent) == 3 and "more good deal" in sent[-1]  # 2 deals + summary line


def test_results_filters_new_only_and_good_only():
    db = _db()
    search = Search(name="s")
    db.add(search)
    db.commit()
    old = _listing(db, "old", 150_000, 40.0)
    new_good = _listing(db, "new good", 150_000, 40.0)
    new_bad = _listing(db, "new bad", 40_000, -30.0)
    new_good.ai_verdict_label = "good"
    new_bad.deal_label = "overpriced"
    old.ai_verdict_label = "good"
    now = datetime.utcnow()
    db.add_all([
        SearchListing(search_id=search.id, listing_id=old.id, found_at=now - timedelta(days=3)),
        SearchListing(search_id=search.id, listing_id=new_good.id, found_at=now - timedelta(hours=1)),
        SearchListing(search_id=search.id, listing_id=new_bad.id, found_at=now - timedelta(hours=1)),
    ])
    db.commit()

    app = FastAPI()
    app.include_router(searches_api.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    def names(**params):
        data = client.get(f"/api/searches/{search.id}/results", params=params).json()
        return sorted(item["subject"] for item in data["items"])

    assert names() == ["new bad", "new good", "old"]
    assert names(new_only=True) == ["new bad", "new good"]
    assert names(new_only=True, good_only=True) == ["new good"]
    assert names(new_only=True, new_within="7d") == ["new bad", "new good", "old"]
    flags = {i["subject"]: i["is_new"] for i in client.get(f"/api/searches/{search.id}/results").json()["items"]}
    assert flags == {"old": False, "new good": True, "new bad": True}
