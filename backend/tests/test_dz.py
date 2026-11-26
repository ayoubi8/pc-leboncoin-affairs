from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.intelligence import analyze, deal, dz_market
from app.models import Listing, Settings


def _db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _listing(price=300.0):
    return Listing(
        subject="ThinkPad T14",
        price_eur=price,
        specs={"brand": "lenovo", "cpu": "i7-1265u", "ram_gb": 16, "storage_gb": 512},
    )


def test_dz_score_uses_landed_vs_algerian_median(monkeypatch):
    db = _db()
    settings = Settings(id=1, eur_dzd_parallel=280.0, llm_api_key="k")
    listing = _listing()
    db.add_all([settings, listing])
    db.commit()

    calls = []

    def fake(_settings, query, ctx="", terms=""):
        calls.append(query)
        return {"ok": True, "data": {"low_dzd": 100000, "median_dzd": 120000, "high_dzd": 140000,
                                     "confidence": "high", "basis": "used", "note": "ok"},
                "sources": [{"title": "ouedkniss", "url": "https://x"}]}

    monkeypatch.setattr(dz_market, "_call_gemini", fake)
    analyze.apply_dz_comparison(db, settings, listing)

    assert listing.dz_price_median_dzd == 120000
    assert listing.dz_landed_dzd == round(listing_landed(settings, listing) * 280)
    expected = deal.score_from_ratio(listing.dz_landed_dzd, 120000)
    assert listing.deal_score == expected
    assert listing.deal_label == deal.classify(expected)

    # cached: a second analysis does not call Gemini again
    analyze.apply_dz_comparison(db, settings, listing)
    assert len(calls) == 1


def listing_landed(settings, listing):
    from app.logistics import landed
    return landed.compute(settings, listing.price_eur)["total_eur"]


def test_failed_lookup_keeps_euro_score(monkeypatch):
    db = _db()
    settings = Settings(id=1, eur_dzd_parallel=280.0, llm_api_key="k")
    listing = _listing()
    listing.deal_score, listing.deal_label = 55.0, "fair"
    db.add_all([settings, listing])
    db.commit()

    monkeypatch.setattr(dz_market, "_call_gemini", lambda *_: {"ok": False, "error": "HTTP 429"})
    analyze.apply_dz_comparison(db, settings, listing)

    assert listing.dz_price_median_dzd is None
    assert listing.deal_score == 55.0
    assert "429" in dz_market.last_error(db, listing)


def test_implausible_prices_rejected(monkeypatch):
    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    listing = _listing()
    db.add_all([settings, listing])
    db.commit()
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *_: {"ok": True, "data": {"median_dzd": 85}, "sources": []})
    assert dz_market.lookup(db, settings, listing) is None


def test_no_key_means_no_lookup(monkeypatch):
    monkeypatch.setattr(dz_market, "OPENROUTER_API_KEY", "")
    assert dz_market.available(Settings(id=1, dz_price_enabled=True, llm_api_key="")) is False
    assert dz_market.available(Settings(id=1, dz_price_enabled=True, llm_api_key="k")) is True
