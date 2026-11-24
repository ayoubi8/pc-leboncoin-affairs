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
    out = enrich.start(db, db.get(Search, 1), settings, auto=False, inline=True, session_factory=same_db)  # the Run AI button
    assert out["started"] and len(out["items"]) == 5  # only the 5 freshest of 7
    assert [i["subject"] for i in out["items"]] == [f"RTX 3080 #{n}" for n in range(5)]
    first = out["items"][0]
    assert first["steps"] == {"specs": "done", "price": "done", "verdict": "done"} and first["verdict"] == "good"
    ad = db.get(Listing, out["items"][0]["id"])
    assert ad.ai_description == "A used RTX 3080." and ad.spec_notes["evidence"]["brand"] == "title says Asus"

    enrich.start(db, db.get(Search, 1), settings, auto=True, inline=True, session_factory=same_db)
    again = enrich.start(db, db.get(Search, 1), settings, auto=True, inline=True, session_factory=same_db)
    assert again["started"] is False and again["reason"] == "cooldown"  # opening the page again does not spend again


def test_card_search_needs_the_model_in_the_ad_even_when_the_gpu_spec_is_empty():
    from app.intelligence import match

    search = Search(name="rtx 3080", kind="gpu", gpu="", include_missing_specs=True)
    assert match.hard_fail(search, Listing(list_id="1", subject="Carte graphique Asus gt640 GT640-DCSL-2GD3", specs={}))
    assert not match.hard_fail(search, Listing(list_id="2", subject="Asus TUF RTX3080 10Go", specs={}))
    assert not match.hard_fail(search, Listing(list_id="3", subject="Carte graphique", description="Vends ma RTX 3080 FE", specs={}))


def test_landed_cost_of_a_300_eur_gpu_matches_a_hand_calculation():
    from app.logistics import landed

    settings = Settings(
        eur_dzd_parallel=280, eur_dzd_official=151.2, transfer_fee_eur=0,
        porsay_handling_eur=0, porsay_per_kg_over=5.7, default_packaging_kg=0.3, gpu_weight_kg=1.8, gpu_box_cm=[35, 20, 10],
        porsay_tariff=[{"max_kg": 2, "price_eur": 27.25}, {"max_kg": 5, "price_eur": 41.87}],
    )
    out = landed.compute(settings, 300, kind="gpu")
    assert out["shipping"]["chargeable_kg"] == 2.1 and out["shipping"]["total_eur"] == 41.87
    assert out["total_eur"] == 341.87  # price + shipping, no customs
    assert "customs" not in out and all(row["key"] != "customs" for row in out["breakdown"])


def test_one_price_request_per_product_then_maths_for_every_ad(monkeypatch):
    from app.intelligence import dz_market, enrich
    from app.models import SearchListing

    enrich._failed.clear()
    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    search = Search(name="rtx 3070", kind="gpu", gpu="RTX 3070")
    db.add_all([settings, search])
    db.commit()
    ads = [
        _listing(lid=200 + i, subject=f"RTX 3070 ad {i}", price_eur=150 + i, specs={"gpu": "RTX 3070"}, profit_ask_eur=None, ai_profit_eur=None)
        for i in range(4)
    ]
    ads.append(_listing(lid=210, subject="RTX 3070 8 Go", price_eur=160, specs={"gpu": "RTX 3070", "ram_gb": 8}, profit_ask_eur=None, ai_profit_eur=None))
    db.add_all(ads)
    db.commit()
    db.add_all([SearchListing(search_id=search.id, listing_id=a.id) for a in ads])
    db.commit()
    calls = []
    answer = {"ok": True, "data": {"median_dzd": 75000, "low_dzd": 70000, "high_dzd": 80000, "confidence": "high"}, "sources": []}
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: calls.append(a[1]) or answer)
    from app.intelligence import verdict

    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no verdict model")))

    enrich.run_for(db, settings, search, ads)
    assert len(calls) == 1  # five ads, one product, one request
    assert all(a.dz_price_median_dzd == 75000 and a.profit_ask_eur is not None and a.ai_verdict_label for a in ads)


def test_different_stated_vram_is_a_different_product():
    from app.intelligence import dz_market
    from app.models import DzPrice

    db = _db()
    db.add(DzPrice(cache_key="gpu|rtx 3060|12", ok=True, median_dzd=60000, fetched_at=datetime.utcnow()))
    db.commit()
    assert dz_market._book_row(db, "gpu|rtx 3060|") is not None
    assert dz_market._book_row(db, "gpu|rtx 3060|8") is None


def test_parts_and_wanted_ads_are_not_priced_as_the_product():
    from app.intelligence import screen

    for title in ("3 kits de pads thermiques Kritical pour Gigabyte", "Waterblock Corsair XG7 RGB pour RTX 3080",
                  "Recherche boite rx6800xt fe", "ÉCHANGE RTX 3070 Ti", "✅ Ram Samsung, DDR4 2666V, 32 GO",
                  "Processeur Intel Pentium G4400", "Bloc refroidissement / Radiateur complet EVGA RTX 3080"):
        assert screen.screen(Listing(subject=title, specs={}))["skip"], title
    for title in ("Rtx 3070 aorus master", "Carte graphique Asus tuf RTX 3070 gaming 8go", "PC portable Dell i5 16 Go"):
        assert not screen.screen(Listing(subject=title, specs={}))["skip"], title


def test_only_specific_products_share_a_price():
    from app.intelligence import pricebook as p

    assert p.is_specific("gpu|rtx 3070|") and p.is_specific("laptop|i5g13|16|512|igpu")
    assert not p.is_specific("laptop|?|32|?|igpu")  # could be two RAM sticks
    assert p.is_specific("laptop|i5g13|?|?|igpu") and p.is_specific("model|latitude 5440")
    assert not p.is_specific("title|pc acer")


def test_price_far_below_the_product_value_gets_no_verdict():
    from app.intelligence import verdict

    settings = Settings(id=1, eur_dzd_parallel=280, eur_dzd_official=151.2,
                        default_packaging_kg=0.3, gpu_weight_kg=1.8, laptop_weight_kg=2.5,
                        gpu_box_cm=[35, 20, 10], laptop_box_cm=[40, 30, 8], porsay_tariff=[{"max_kg": 5, "price_eur": 41.87}])
    ad = Listing(subject="Pc acer", price_eur=1, dz_price_median_dzd=86000, dz_confidence="high", specs={})
    assert verdict.apply_math(settings, ad) is False
    assert ad.profit_ask_eur is None and ad.dz_price_median_dzd is None and "suspiciously" in ad.risk_flags[0]


def test_cpu_generations_are_read_correctly():
    from app.intelligence import pricebook as p

    for cpu, tier in (("i5-1335U", "i5g13"), ("i5-1235U", "i5g12"), ("i7-1165G7", "i7g11"), ("i5-1035G1", "i5g10"),
                      ("i5-13420H", "i5g13"), ("i5-8250U", "i5g8"), ("i5 13th Gen", "i5g13"), ("i7-12th gen", "i7g12")):
        assert p.cpu_tier(cpu) == tier, cpu
    assert p.title_cpu("Dell latitude 3550 - i5 13 Gen - 8go") == "i5 13th gen"


def test_named_laptop_models_share_one_key():
    from app.intelligence import pricebook as p

    assert p.model_name("Dell Latitude 5440") == "latitude 5440"
    assert p.model_name("Dell Inspiron 14 7430 2-en-1") == "inspiron 7430"
    assert p.model_name("Pc portable HP EliteBook 840 G10") == "elitebook 840 g10"
    assert p.model_name("Lenovo ThinkPad T14 Gen 3") == "thinkpad t14 g3"
    assert p.model_name("Ordinateur portable Dell") == ""
    a = Listing(subject="Dell Latitude 5440", specs={})
    b = Listing(subject="dell latitude 5440 tres bon etat", specs={})
    assert p.canonical(a)[0] == p.canonical(b)[0] == "model|latitude 5440"


def test_unknown_ram_uses_the_cheapest_config_of_that_cpu_at_low_confidence():
    from app.intelligence import dz_market
    from app.models import DzPrice

    db = _db()
    db.add_all([
        DzPrice(cache_key="laptop|i5g13|16|512|igpu", ok=True, median_dzd=90000, confidence="high", fetched_at=datetime.utcnow()),
        DzPrice(cache_key="laptop|i5g13|8|256|igpu", ok=True, median_dzd=70000, confidence="high", fetched_at=datetime.utcnow()),
    ])
    db.commit()
    assert dz_market._book_row(db, "laptop|i5g13|?|?|igpu").median_dzd == 70000
    from app.intelligence import pricebook

    assert pricebook.is_estimate("laptop|i5g13|?|?|igpu") and not pricebook.is_estimate("laptop|i5g13|16|512|igpu")


def test_out_of_credit_never_wipes_a_price_or_blames_the_product(monkeypatch):
    from app.intelligence import dz_market
    from app.models import DzPrice

    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    old = datetime.utcnow() - timedelta(days=30)
    db.add_all([settings, DzPrice(cache_key="gpu|rtx 3070|", ok=True, median_dzd=75000, confidence="high", fetched_at=old)])
    db.commit()
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: {"ok": False, "error": "OpenRouter HTTP 402: limit"})
    ad = Listing(list_id="1", subject="RTX 3070", specs={"gpu": "RTX 3070"})
    assert dz_market.lookup(db, settings, ad).median_dzd == 75000
    assert db.query(DzPrice).filter_by(cache_key="gpu|rtx 3070|").one().ok is True
    assert "out of credit" in dz_market.last_error(db, ad)
    dz_market._temporary.clear()


def test_daily_lookup_cap_stops_spending_but_not_the_price_button(monkeypatch):
    from app.intelligence import dz_market
    from app.models import DzPrice

    db = _db()
    settings = Settings(id=1, llm_api_key="k", dz_lookups_per_day=2)
    db.add_all([settings] + [DzPrice(cache_key=f"gpu|x{i}|", ok=True, median_dzd=1, fetched_at=datetime.utcnow()) for i in range(2)])
    db.commit()
    calls = []
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: calls.append(1) or {"ok": False, "error": "no price"})
    ad = Listing(list_id="1", subject="RTX 3070", specs={"gpu": "RTX 3070"})
    assert dz_market.lookup(db, settings, ad) is None and calls == []
    assert "Daily limit" in dz_market.last_error(db, ad)
    dz_market.lookup(db, settings, ad, force=True)
    assert calls == [1]
    dz_market._temporary.clear()


def test_out_of_credit_raises_a_system_alert(monkeypatch):
    from app.intelligence import dz_market
    from app.notify import system

    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    db.add(settings)
    db.commit()
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: {"ok": False, "error": "OpenRouter HTTP 402: limit"})
    dz_market.lookup(db, settings, Listing(list_id="1", subject="RTX 3070", specs={"gpu": "RTX 3070"}))
    kinds = [p["kind"] for p in system.compute_health(db, settings)["problems"]]
    assert "openrouter_no_credit" in kinds
    dz_market._no_credit_at = None
    dz_market._temporary.clear()


def test_no_stale_alert_right_after_a_restart(monkeypatch):
    from app.notify import system

    db = _db()
    settings = Settings(id=1, auto_check_enabled=True, llm_api_key="k")
    db.add_all([settings, Search(name="pc", auto_check_enabled=True, interval="1h"),
                Run(search_id=1, status="success", finished_at=datetime.utcnow() - timedelta(hours=12))])
    db.commit()
    monkeypatch.setattr(system.progress, "uptime_seconds", lambda: 60)
    assert "scan_stale" not in [p["kind"] for p in system.compute_health(db, settings)["problems"]]
    monkeypatch.setattr(system.progress, "uptime_seconds", lambda: 3600)
    assert "scan_stale" in [p["kind"] for p in system.compute_health(db, settings)["problems"]]


def test_scheduler_skips_a_search_that_is_already_scanning(monkeypatch):
    from app import scheduler

    _reset()
    db = _db()
    db.add_all([Settings(id=1, auto_check_enabled=True), Search(name="busy", auto_check_enabled=True, interval="1h")])
    db.commit()
    from contextlib import contextmanager

    @contextmanager
    def same_db():
        yield db

    monkeypatch.setattr(scheduler, "SessionLocal", same_db)
    monkeypatch.setattr(scheduler, "housekeeping", lambda *a: None)
    monkeypatch.setattr(scheduler, "run_search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    progress.start_run(1, 1, "busy", 1, "manual")
    assert scheduler.check_due_searches()["ran"] == []
    progress.end_run(1, "success")
