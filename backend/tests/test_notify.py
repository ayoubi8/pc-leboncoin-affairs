from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import searches as searches_api
from app.db import Base, get_db
from app.extraction import llm
from app.intelligence import verdict
from app.models import Listing, Search, SearchListing, Settings
from app.notify import deals, telegram


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _setup(db, **overrides):
    settings = Settings(id=1, telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="1", llm_api_key="k", **overrides)
    search = Search(name="s", notify_telegram=True)
    db.add_all([settings, search])
    db.commit()
    return settings, search


def _paris(hours_ago: float) -> str:
    """Leboncoin-style timestamp (Paris time, UTC+1 in winter) for an ad published `hours_ago` hours ago."""
    return (datetime.utcnow() - timedelta(hours=hours_ago) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")


def _listing(db, subject, dz_median, price=220.0, hours_ago=1.0, **kw):
    listing = Listing(
        subject=subject, price_eur=price, url="https://lbc/x", first_publication_date=_paris(hours_ago),
        specs={"cpu": "i5-13420h", "ram_gb": 16}, dz_price_median_dzd=dz_median, dz_price_low_dzd=dz_median * 0.9,
        dz_price_high_dzd=dz_median * 1.1, dz_confidence="medium", images=[], ship_ok="yes",
        first_seen_at=datetime.utcnow(), **kw,
    )
    listing.freshness_score = 90.0
    db.add(listing)
    db.commit()
    return listing


class Sink:
    def __init__(self, monkeypatch, online="active", ok=True):
        self.sent = []
        self.checked = []
        self.ok = ok
        monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: None)  # rule-based verdicts
        monkeypatch.setattr(llm, "available", lambda s: False)  # template negotiation message, no network
        monkeypatch.setattr(telegram, "send_message", self.send)
        monkeypatch.setattr(deals, "_check_online", lambda l: self.checked.append(l.id) or online)

    def send(self, settings, text, photo_url=None, buttons=None, reply_to=None):
        self.sent.append({"text": text, "buttons": buttons or [], "reply_to": reply_to})
        return {"ok": True, "result": {"message_id": len(self.sent)}} if self.ok else {"ok": False, "error": "boom"}


def test_only_profitable_fresh_deals_are_sent_once(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    good = _listing(db, "Great <b>laptop</b>", 150_000)
    bad = _listing(db, "Meh laptop", 40_000)
    sink = Sink(monkeypatch)

    stats = deals.notify_run(db, settings, search, [good, bad])
    assert stats["sent"] == 1
    alert, message = sink.sent[0], sink.sent[1]  # alert + the copy-paste negotiation message
    assert "&lt;b&gt;laptop&lt;/b&gt;" in alert["text"]  # ad text is HTML-escaped
    assert "<code>" in message["text"] and message["reply_to"] == 1
    labels = [b[0] for b in alert["buttons"]]
    assert "Open ad" in labels and "📨 Contacted" in labels and "✅ Bought" in labels
    assert f"cb:p:b:{good.id}" in [b[1] for b in alert["buttons"]]
    assert good.notified_at is not None and bad.notified_at is None
    assert good.price_alerted_eur == 220.0

    assert deals.notify_run(db, settings, search, [good, bad])["sent"] == 0  # never alerted twice


def test_stale_or_unshippable_or_rejected_ads_never_alert(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    old = _listing(db, "old", 150_000, hours_ago=24 * 10)
    pickup = _listing(db, "pickup", 150_000)
    pickup.ship_ok = "no"
    rejected = _listing(db, "rejected", 150_000)
    rejected.screen_skip = "broken / for parts"
    scam = _listing(db, "scam", 150_000)
    scam.risk_flags = ["suspiciously cheap (<35% of market)"]
    db.commit()
    sink = Sink(monkeypatch)
    assert deals.notify_run(db, settings, search, [old, pickup, rejected, scam])["sent"] == 0
    assert sink.sent == [] and sink.checked == []  # no paid/verification call for free-gate rejects

    settings.alert_pickup_only = True
    db.commit()
    assert deals.notify_run(db, settings, search, [pickup])["sent"] == 1


def test_ad_that_is_gone_is_not_alerted_and_is_marked(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    ad = _listing(db, "gone soon", 150_000)
    sink = Sink(monkeypatch, online="gone")
    stats = deals.notify_run(db, settings, search, [ad])
    assert stats["sent"] == 0 and stats["gone"] == 1 and sink.sent == []
    assert ad.gone_at is not None and ad.is_active is False and ad.notified_at is None


def test_unverified_availability_is_flagged_but_sent(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    ad = _listing(db, "maybe", 150_000)
    sink = Sink(monkeypatch, online="unknown")
    assert deals.notify_run(db, settings, search, [ad])["sent"] == 1
    assert "not verified" in sink.sent[0]["text"]


def test_deal_that_only_works_after_haggling_is_skipped(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    # resale ~ landed cost: profitable only if the seller drops the price a lot
    thin = _listing(db, "thin", 79_000)
    Sink(monkeypatch)
    numbers = verdict.compute_numbers(settings, thin)
    assert numbers["profit_ask_eur"] < numbers["profit_eur"]
    assert deals.notify_run(db, settings, search, [thin])["sent"] == 0


def test_price_drop_realerts_a_known_ad(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    ad = _listing(db, "dropper", 150_000, price=240.0)
    sink = Sink(monkeypatch)
    assert deals.notify_run(db, settings, search, [ad])["sent"] == 1
    n_before = len(sink.sent)

    ad.price_eur = 232.0  # only -3 %: no new alert
    assert deals.notify_run(db, settings, search, [], [ad])["sent"] == 0
    ad.price_eur = 200.0  # -17 %: alert again
    assert deals.notify_run(db, settings, search, [], [ad])["sent"] == 1
    assert "PRICE DROP" in sink.sent[n_before]["text"] and ad.price_alerted_eur == 200.0


def test_cap_per_run_and_quiet_hours(monkeypatch):
    db = _db()
    settings, search = _setup(db, notify_max_per_run=2)
    items = [_listing(db, f"L{i}", 150_000 + i * 1000) for i in range(4)]
    sink = Sink(monkeypatch)
    assert deals.notify_run(db, settings, search, items)["sent"] == 2
    assert "more good deal" in sink.sent[-1]["text"]

    db2 = _db()
    settings2, search2 = _setup(db2, quiet_start_hour=0, quiet_end_hour=24)  # always quiet
    ad = _listing(db2, "night", 150_000)
    sink2 = Sink(monkeypatch)
    stats = deals.notify_run(db2, settings2, search2, [ad])
    assert stats["sent"] == 0 and stats["quiet"] == 1 and sink2.sent == [] and ad.notified_at is None


def test_quiet_hours_window_wraps_midnight():
    settings = Settings(quiet_start_hour=23, quiet_end_hour=7)
    assert deals.in_quiet_hours(settings, datetime(2026, 11, 20, 23, 30))  # 00:30 Algeria
    assert not deals.in_quiet_hours(settings, datetime(2026, 11, 20, 12, 0))
    assert not deals.in_quiet_hours(Settings(), datetime(2026, 11, 20, 3, 0))


def test_failed_send_is_retried_next_run(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    good = _listing(db, "Great laptop", 150_000)
    Sink(monkeypatch, ok=False)
    assert deals.notify_run(db, settings, search, [good])["sent"] == 0
    assert good.notified_at is None


def test_results_filters_new_only_and_good_only():
    db = _db()
    search = Search(name="s")
    db.add(search)
    db.commit()
    old = _listing(db, "old", 150_000)
    new_good = _listing(db, "new good", 150_000)
    new_bad = _listing(db, "new bad", 40_000)
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


def test_unpriced_fresh_ad_is_priced_and_judged_before_the_alert(monkeypatch):
    """Scans do no AI by themselves; the alert step prices and judges the freshest new ads first."""
    from app.intelligence import enrich

    db = _db()
    settings, search = _setup(db)
    fresh = _listing(db, "Fresh unpriced laptop", 150_000)
    fresh.dz_price_median_dzd = fresh.dz_price_low_dzd = fresh.dz_price_high_dzd = None  # nothing priced yet
    db.commit()
    sink = Sink(monkeypatch)
    ai = {"verdict": "great", "headline": "Solid margin", "opinion": "Buy it, resale is strong.", "risks": [], "max_buy_price_eur": 230}
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: ai)

    def fake_ai(db_, settings_, search_, listings, limit=5):
        for l in listings:
            l.dz_price_median_dzd, l.dz_price_low_dzd, l.dz_price_high_dzd, l.dz_confidence = 150_000, 135_000, 165_000, "medium"
            verdict.apply(db_, settings_, l)  # the Haiku step (stubbed)
        return len(listings)

    monkeypatch.setattr(enrich, "run_for", fake_ai)
    stats = deals.notify_run(db, settings, search, [fresh])
    assert stats["sent"] == 1 and stats["ai_checked"] == 1
    text = sink.sent[0]["text"]
    assert "Solid margin" in text and "Buy it, resale is strong." in text
    assert "Open ad" in [b[0] for b in sink.sent[0]["buttons"]]


def test_send_best_deals_now_alerts_fresh_ads_already_in_the_search(monkeypatch):
    db = _db()
    settings, search = _setup(db)
    good = _listing(db, "Good laptop already stored", 150_000)
    old = _listing(db, "Old laptop", 150_000, hours_ago=200)
    db.add_all([SearchListing(search_id=search.id, listing_id=good.id), SearchListing(search_id=search.id, listing_id=old.id)])
    db.commit()
    sink = Sink(monkeypatch)
    app = FastAPI()
    app.include_router(searches_api.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    out = client.post(f"/api/searches/{search.id}/alert-now").json()
    assert out["sent"] == 1 and out["fresh"] == 1  # the 200 h old ad is not even considered
    assert "Good laptop already stored" in sink.sent[0]["text"]
    assert client.post(f"/api/searches/{search.id}/alert-now").json()["sent"] == 0  # never twice
