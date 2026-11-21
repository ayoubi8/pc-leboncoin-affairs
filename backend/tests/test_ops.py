from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import ops
from app.db import Base, get_db
from app.intelligence import analyze, dz_market
from app.models import DzPrice, Listing, Run, Search, Settings
from app.notify import pipeline, poller, system, telegram


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _settings(db, **kw):
    settings = Settings(id=1, telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="42", llm_api_key="k", **kw)
    db.add(settings)
    db.commit()
    return settings


def test_blocked_streak_and_rejected_key_raise_alerts_once(monkeypatch):
    db = _db()
    settings = _settings(db)
    db.add(Search(name="s", auto_check_enabled=True, interval="1h"))
    now = datetime.utcnow()
    db.add(Run(search_id=1, status="success", finished_at=now - timedelta(hours=5)))
    db.add_all([Run(search_id=1, status="blocked", finished_at=now) for _ in range(3)])
    db.add(DzPrice(cache_key="a", ok=False, note="OpenRouter HTTP 401: User not found.", fetched_at=now))
    db.commit()

    health = system.compute_health(db, settings)
    kinds = {p["kind"] for p in health["problems"]}
    assert {"scanner_blocked", "key_rejected", "scan_stale"} <= kinds and not health["ok"]

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda s, text, **k: sent.append(text) or {"ok": True})
    assert set(system.check_and_alert(db, settings)) == kinds
    assert len(sent) == len(kinds)
    assert system.check_and_alert(db, settings) == []  # no spam: reminder only after 24 h

    db.add(Run(search_id=1, status="success", finished_at=datetime.utcnow()))
    db.add(DzPrice(cache_key="b", ok=True, median_dzd=100000, fetched_at=datetime.utcnow() + timedelta(seconds=1)))
    db.commit()
    system.check_and_alert(db, settings)
    assert any("Resolved" in t for t in sent)  # recovery message
    assert system.compute_health(db, settings)["ok"]


def _update(uid, **body):
    return {"update_id": uid, **body}


def test_buttons_and_commands_update_the_pipeline(monkeypatch):
    db = _db()
    settings = _settings(db)
    ad = Listing(subject="PC", price_eur=300.0, url="u", dz_price_median_dzd=150000, specs={"cpu": "i5"})
    db.add(ad)
    db.commit()
    replies, answers = [], []
    monkeypatch.setattr(telegram, "send_message", lambda s, text, **k: replies.append(text) or {"ok": True})
    monkeypatch.setattr(telegram, "answer_callback", lambda t, i, text="": answers.append(text) or {"ok": True})
    chat = {"id": 42}
    updates = [
        _update(10, callback_query={"id": "c1", "data": f"p:c:{ad.id}", "message": {"chat": chat}}),
        _update(11, callback_query={"id": "c2", "data": f"p:b:{ad.id}", "message": {"chat": {"id": 999}}}),  # stranger
        _update(12, message={"chat": chat, "text": f"/paid {ad.id} 270"}),
        _update(13, message={"chat": chat, "text": f"/sold {ad.id} 120000"}),
        _update(14, message={"chat": {"id": 999}, "text": f"/paid {ad.id} 1"}),  # stranger
    ]
    monkeypatch.setattr(telegram, "get_updates", lambda token, offset=0: {"ok": True, "result": updates})

    assert poller.process_updates(db, settings) == 5
    assert settings.telegram_update_offset == 15
    assert ad.pipeline_status == "sold" and ad.bought_price_eur == 270 and ad.sold_price_dzd == 120000
    assert answers[0].startswith("Marked as contacted") and answers[1] == "Not allowed"
    assert any("Realised profit" in r for r in replies)

    # without a chat id nothing is processed
    settings.telegram_chat_id = ""
    assert poller.process_updates(db, settings) == 0


def test_learning_from_outcomes_needs_three_samples():
    db = _db()
    settings = _settings(db)
    for i, (ask, paid, sold) in enumerate([(200, 180, 50000), (300, 270, 70000), (250, 225, 60000)]):
        listing = Listing(subject=f"p{i}", price_eur=ask, dz_price_median_dzd=60000 if i != 1 else 80000, specs={"cpu": "i5"})
        db.add(listing)
        db.commit()
        pipeline.set_status(db, settings, listing, "sold", bought_price_eur=paid, sold_price_dzd=sold)
        if i < 2:
            assert settings.avg_discount_pct == 6.0 and settings.resale_haircut_pct == 10.0  # not enough data yet
    assert settings.avg_discount_pct == 10.0  # sellers really gave 10 %
    assert settings.resale_haircut_pct == 9.7  # mean of 16.7 %, 12.5 % and 0 % below the asking median
    realised = pipeline.realised_profit(settings, listing)
    assert realised and realised["revenue_eur"] == round(60000 / 280, 2)


def test_manual_price_overrides_gemini_for_every_similar_ad(monkeypatch):
    db = _db()
    settings = _settings(db)
    a = Listing(subject="A", price_eur=250.0, specs={"cpu": "i5-13420h", "ram_gb": 16, "storage_gb": 512})
    b = Listing(subject="B", price_eur=260.0, specs={"cpu": "i5-13500h", "ram_gb": 16, "storage_gb": 512})  # same tier/buckets
    db.add_all([a, b])
    db.commit()
    gemini = []
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *x: gemini.append(1) or {"ok": True, "data": {"median_dzd": 90000}, "sources": []})

    app = FastAPI()
    app.include_router(ops.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    assert client.put(f"/api/listings/{a.id}/dz-price", json={"median_dzd": 120000}).json()["dz_price_median_dzd"] == 120000
    analyze.apply_dz_comparison(db, settings, b)
    assert b.dz_price_median_dzd == 120000 and gemini == []  # same product key: manual price, no Gemini call
    analyze.apply_dz_comparison(db, settings, b, force=True)
    assert b.dz_price_median_dzd == 120000 and gemini == []  # even a forced refresh never overwrites it

    rows = client.get("/api/price-book").json()
    assert rows[0]["manual"] is True and rows[0]["key"].startswith("laptop|i5g13|16|512")


def test_listing_detail_tolerates_null_columns():
    """Listings saved before newer columns existed hold NULLs; must not 500."""
    from app.schemas import ListingDetail

    class Row:
        id = 1
        subject = "old ad"
        dz_sources = None
        risk_flags = None
        images = None
        specs = None
        is_active = None
        repost_count = None
        screen_skip = None
        price_eur = None

    d = ListingDetail.model_validate(Row())
    assert d.dz_sources == [] and d.risk_flags == [] and d.images == []
    assert d.specs == {} and d.is_active is True and d.repost_count == 0
    assert d.price_eur is None
