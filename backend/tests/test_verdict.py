from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.intelligence import verdict
from app.models import Listing, Settings


def _settings():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    settings = Settings(id=1)  # persisted so column defaults (shipping rates etc.) apply
    db.add(settings)
    db.commit()
    return settings


def _listing(dz=80000):
    return Listing(subject="ThinkPad", price_eur=220.0, dz_price_median_dzd=dz,
                   dz_price_low_dzd=dz and dz * 0.9, dz_price_high_dzd=dz and dz * 1.1, dz_confidence="medium",
                   specs={"cpu": "i5", "ram_gb": 16})


def test_numbers_convert_dzd_to_eur_and_compute_profit():
    n = verdict.compute_numbers(_settings(), _listing(), buy_price_eur=200)
    assert n["dz_median_eur"] == round(80000 / 280, 2)
    assert n["buy_price_eur"] == 200
    assert n["negotiation_saving_eur"] == 20
    assert abs(n["profit_eur"] - (n["dz_net_eur"] - n["total_cost_eur"])) < 0.02
    assert n["dz_net_eur"] == round(n["dz_median_eur"] * 0.9, 2)  # 10 % resale haircut by default
    assert n["total_cost_eur"] > 200  # shipping added


def test_no_algerian_price_means_no_numbers():
    assert verdict.compute_numbers(_settings(), _listing(dz=None)) is None


def test_label_thresholds():
    assert verdict.label_for(40, "high") == "great"
    assert verdict.label_for(40, "low") == "good"
    assert verdict.label_for(8, "high") == "fair"
    assert verdict.label_for(-3, "high") == "skip"


def test_rules_fallback_when_model_down(monkeypatch):
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: None)
    out = verdict.generate(_settings(), _listing(), 200)
    assert out["source"] == "rules" and out["verdict"] in ("great", "good", "fair", "skip")


def test_model_cannot_beat_the_numbers(monkeypatch):
    monkeypatch.setattr(verdict, "_ask_model", lambda *a, **k: {"verdict": "great", "headline": "x", "opinion": "y", "risks": []})
    out = verdict.generate(_settings(), _listing(dz=20000), 200)  # resale far below cost
    assert out["verdict"] == "skip"


def test_conservative_profit_and_default_discount():
    settings = _settings()
    n = verdict.compute_numbers(settings, _listing())  # no explicit buy price: ask - 6 %
    assert n["buy_price_eur"] == round(220 * 0.94, 2)
    assert n["profit_ask_eur"] < n["profit_eur"]  # buying at the full ask earns less
    assert n["total_cost_ask_eur"] > n["total_cost_eur"]
    settings.resale_haircut_pct = 0
    settings.avg_discount_pct = 0
    flat = verdict.compute_numbers(settings, _listing())
    assert flat["profit_ask_eur"] == flat["profit_eur"] and flat["dz_net_eur"] == flat["dz_median_eur"]
