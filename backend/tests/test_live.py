from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import progress
from app.api import ops
from app.db import Base, get_db
from app.intelligence import keycheck
from app.models import Listing, Run, Search, Settings


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _client(db):
    app = FastAPI()
    app.include_router(ops.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _reset():
    progress._runs.clear()
    progress._events.clear()


def test_progress_bar_moves_through_stages_and_logs_events():
    _reset()
    progress.start_run(1, 7, "pc i5", queries_total=2, trigger="manual")
    progress.update_run(1, stage="fetching", queries_done=1, detail="query 2/2, page 1")
    mid = progress.running()[0]
    assert 5 < mid["pct"] < 70 and "query 2/2" in mid["stage_label"]

    progress.update_run(1, stage="pricing", ads_done=5, ads_total=10, detail="ad 6/10")
    priced = progress.running()[0]
    assert 70 < priced["pct"] < 94

    progress.end_run(1, "success", new_count=3, total=40)
    assert progress.running() == []  # a finished scan leaves the running list...
    assert "40 ads checked, 3 new" in progress.events()[0]["message"]  # ...and lands in the feed


def test_failed_scan_is_logged_as_an_error():
    _reset()
    progress.start_run(2, 1, "gpu", 1, "auto")
    progress.end_run(2, "blocked", error="DataDome")
    event = progress.events()[0]
    assert event["level"] == "error" and "blocked" in event["message"]


def test_live_endpoint_reports_running_scan_and_next_due():
    _reset()
    db = _db()
    db.add(Settings(id=1, llm_api_key="k"))
    db.add(Search(name="pc", auto_check_enabled=True, interval="15m", last_run_at=datetime.utcnow() - timedelta(minutes=5)))
    db.commit()
    progress.start_run(9, 1, "pc", 1, "manual")

    data = _client(db).get("/api/live").json()
    assert data["running"][0]["search_name"] == "pc"
    assert data["next"] is None  # the only search is busy, so nothing else is "next"
    assert data["auto_enabled"] is True

    progress.end_run(9, "success")
    data = _client(db).get("/api/live").json()
    assert data["running"] == []
    assert 0 < data["next"]["due_in_s"] <= 10 * 60  # 15 min interval, 5 min ago


def _listing(**kw):
    base = dict(
        list_id=str(kw.pop("lid")),
        subject="PC",
        price_eur=240,
        first_publication_date=(datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        index_date=(datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        freshness_score=90,
        profit_ask_eur=60,
        ai_profit_eur=80,
        is_active=True,
    )
    base.update(kw)
    return Listing(**base)


def test_act_now_only_lists_fresh_profitable_actionable_ads():
    db = _db()
    db.add(Settings(id=1))
    db.add_all([
        _listing(lid=1, subject="good one"),
        _listing(lid=2, subject="loss", profit_ask_eur=-20, ai_profit_eur=-5),
        _listing(lid=3, subject="sold", gone_at=datetime.utcnow(), is_active=False),
        _listing(lid=4, subject="pickup only", ship_ok="no"),
        _listing(lid=5, subject="already bought", pipeline_status="bought"),
        _listing(lid=6, subject="screened out", screen_skip="accessory"),
        _listing(lid=7, subject="unpriced", profit_ask_eur=None, ai_profit_eur=None),
        _listing(lid=8, subject="stale", first_publication_date="2020-01-01 10:00:00", index_date="2020-01-01 10:00:00"),
    ])
    db.commit()

    data = _client(db).get("/api/deals/act-now").json()
    assert [i["subject"] for i in data["items"]] == ["good one"]
    assert data["unpriced_fresh"] == 1  # surfaced so the UI can say "waiting for a price"


def test_manual_run_async_returns_immediately_and_refuses_double_start(monkeypatch):
    _reset()
    db = _db()
    db.add(Settings(id=1))
    db.add(Search(name="pc"))
    db.commit()

    from app.api import searches

    app = FastAPI()
    app.include_router(searches.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    started = []
    monkeypatch.setattr(searches, "run_search", lambda *a, **k: started.append(k))
    progress.start_run(5, 1, "pc", 1, "manual")  # already scanning
    assert client.post("/api/searches/1/run-async").json() == {"started": False, "already_running": True}
    progress.end_run(5, "success")

    assert client.post("/api/searches/1/run-async").json()["started"] is True


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_management_key_is_named_as_the_problem(monkeypatch):
    def fake_get(url, **k):
        return _Resp(200, {"data": {"is_management_key": True}})

    def fake_post(url, **k):
        return _Resp(401, {"error": {"message": "User not found."}})

    monkeypatch.setattr(keycheck.httpx, "get", fake_get)
    monkeypatch.setattr(keycheck.httpx, "post", fake_post)
    result = keycheck.check_openrouter("sk-or-v1-x")
    assert result["ok"] is False
    assert "management key" in result["message"]
    assert [s["ok"] for s in result["steps"]] == [True, False, False, False]  # key ok, then each model call fails


def test_working_key_passes_both_model_calls(monkeypatch):
    monkeypatch.setattr(keycheck.httpx, "get", lambda *a, **k: _Resp(200, {"data": {"is_management_key": False}}))
    monkeypatch.setattr(keycheck.httpx, "post", lambda *a, **k: _Resp(200, {"choices": []}))
    assert keycheck.check_openrouter("sk-or-v1-x")["ok"] is True


def test_missing_key_is_reported_without_network(monkeypatch):
    monkeypatch.setattr(keycheck.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    assert keycheck.check_openrouter("")["ok"] is False


def test_saving_settings_keeps_the_tariff_well_formed():
    from app.api import settings as settings_api

    db = _db()
    db.add(Settings(id=1))
    db.commit()
    app = FastAPI()
    app.include_router(settings_api.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    payload = {"porsay_tariff": [{"up_to_kg": 2, "price_eur": 27.25}, {"max_kg": 5, "price_eur": 41.87, "junk": 1}, {"price_eur": 9}]}
    saved = client.put("/api/settings", json=payload).json()["porsay_tariff"]
    assert saved == [{"max_kg": 2.0, "price_eur": 27.25}, {"max_kg": 5.0, "price_eur": 41.87}]


def test_gpu_search_without_gpu_field_uses_the_model_in_its_name():
    from app.search.query_generator import generate_queries, wanted_gpu

    search = Search(name="rtx 3080", kind="gpu", gpu="")
    assert wanted_gpu(search) == "RTX 3080"
    assert [q.text for q in generate_queries(search)][0] == "RTX 3080"
    assert wanted_gpu(Search(name="rtx 3080", kind="laptop", gpu="")) == ""  # laptops never guess from the name


def test_gpu_search_rejects_other_cards():
    from app.intelligence import match

    search = Search(name="rtx 3080", kind="gpu", gpu="", include_missing_specs=True)
    assert match.hard_fail(search, Listing(list_id="1", subject="RX 580", specs={"gpu": "RX 580"}))
    assert not match.hard_fail(search, Listing(list_id="2", subject="RTX 3080 FE", specs={"gpu": "RTX 3080"}))


def test_scans_use_no_ai_and_read_only_the_price_cache(monkeypatch):
    from app.intelligence import dz_market

    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    db.add(settings)
    db.commit()
    calls = []
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: calls.append(1) or {"ok": False, "error": "x"})
    listing = Listing(list_id="1", subject="carte graphique", specs={"gpu": "RTX 3080"})
    assert dz_market.lookup(db, settings, listing, allow_call=False) is None
    assert calls == []
    dz_market.lookup(db, settings, listing)  # an explicit lookup does call the model
    assert calls == [1]


def test_enrich_runs_three_steps_on_the_freshest_ads_only(monkeypatch):
    from app.extraction import llm
    from app.intelligence import enrich, verdict

    enrich._jobs.clear()
    enrich._last_auto.clear()
    enrich._failed.clear()
    db = _db()
    db.add(Settings(id=1, llm_api_key="k"))
    db.add(Search(name="rtx 3080", kind="gpu"))
    db.commit()
    for i in range(7):
        hours = 2 + i
        stamp = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        db.add(_listing(lid=100 + i, subject=f"RTX 3080 #{i}", specs={"gpu": "RTX 3080"}, first_publication_date=stamp, index_date=stamp,
                        profit_ask_eur=None, ai_profit_eur=None))
    db.commit()
    from app.models import SearchListing
    for l in db.query(Listing).all():
        db.add(SearchListing(search_id=1, listing_id=l.id))
    db.commit()

    monkeypatch.setattr(llm, "extract_specs_detailed", lambda *a, **k: {
        "ok": True, "model": "free/model", "specs": {"brand": "Asus"}, "evidence": {"brand": "title says Asus"}, "description": "A used RTX 3080.", "error": ""})
    monkeypatch.setattr(enrich.analyze, "apply_dz_comparison", lambda db_, s, l, allow_call=True, **k: allow_call and setattr(l, "dz_price_median_dzd", 150000))  # scans (allow_call=False) never price
    monkeypatch.setattr(enrich.verdict, "apply", lambda db_, s, l, **k: setattr(l, "ai_verdict", {"source": "ai"}) or {"verdict": "good", "source": "ai", "model": "haiku"})

    from contextlib import contextmanager

    @contextmanager
    def same_db():  # the job must use THIS test database, never the real app.db
        yield db

    settings = db.get(Settings, 1)
    out = enrich.start(db, db.get(Search, 1), settings, auto=True, inline=True, session_factory=same_db)
    assert out["started"] and len(out["items"]) == 5  # only the 5 freshest of 7
    assert [i["subject"] for i in out["items"]] == [f"RTX 3080 #{n}" for n in range(5)]
    first = out["items"][0]
    assert first["steps"] == {"specs": "done", "price": "done", "verdict": "done"} and first["verdict"] == "good"
    ad = db.get(Listing, out["items"][0]["id"])
    assert ad.ai_description == "A used RTX 3080." and ad.spec_notes["evidence"]["brand"] == "title says Asus"

    again = enrich.start(db, db.get(Search, 1), settings, auto=True, inline=True, session_factory=same_db)
    assert again["started"] is False and again["reason"] == "cooldown"  # opening the page again does not spend again


def test_card_search_needs_the_model_in_the_ad_even_when_the_gpu_spec_is_empty():
    from app.intelligence import match

    search = Search(name="rtx 3080", kind="gpu", gpu="", include_missing_specs=True)
    assert match.hard_fail(search, Listing(list_id="1", subject="Carte graphique Asus gt640 GT640-DCSL-2GD3", specs={}))
    assert not match.hard_fail(search, Listing(list_id="2", subject="Asus TUF RTX3080 10Go", specs={}))
    assert not match.hard_fail(search, Listing(list_id="3", subject="Carte graphique", description="Vends ma RTX 3080 FE", specs={}))
