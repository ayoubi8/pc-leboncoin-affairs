from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.intelligence import dz_market, enrich, pricebook
from app.models import DzPrice, Listing, Search, SearchListing, Settings


def _db():
    engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _card(subject, vram=None, price=250.0):
    specs = {"gpu": "RTX 3070"}
    if vram:
        specs["ram_gb"] = vram
    return Listing(subject=subject, price_eur=price, specs=specs, url="u", images=[])


def test_median_comes_from_the_listed_prices_without_other_variants_or_outliers():
    answer = {"prices": [
        {"title": "MSI RTX 3070 Gaming X Trio", "price_dzd": 73000, "condition": "used"},
        {"title": "ASUS RTX 3070 8GB OC (Occasion)", "price_dzd": 83900, "condition": "used"},
        {"title": "RTX 3070 Galax", "price_dzd": 86950, "condition": "used"},
        {"title": "ASUS TUF RTX 3070 OC", "price_dzd": 93000, "condition": "used"},
        {"title": "RTX 3070 Ti Gigabyte", "price_dzd": 98900, "condition": "used"},  # other variant
        {"title": "PC portable gamer RTX 3070", "price_dzd": 190000, "condition": "used"},  # a laptop
        {"title": "RTX 3070", "price_dzd": 25000, "condition": "used"},  # outlier
    ]}
    found = dz_market.summarize(answer, "gpu|rtx 3070|")
    assert found["median"] == (83900 + 86950) / 2
    assert found["samples"] == 4 and found["dropped"] == 3 and found["confidence"] == "high"
    assert (found["low"], found["high"]) == (73000, 93000)
    ti = dz_market.summarize(answer, "gpu|rtx 3070 ti|")
    assert ti["median"] == 98900 and ti["confidence"] == "low"
    assert dz_market.summarize({"prices": []}, "gpu|rtx 3070|") is None
    assert dz_market.summarize({"median_dzd": 80000, "confidence": "high"}, "gpu|rtx 3070|")["median"] == 80000  # old format


def test_a_recheck_that_finds_nothing_keeps_the_old_price(monkeypatch):
    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    db.add_all([settings, DzPrice(cache_key="gpu|rtx 4050|", ok=True, median_dzd=60000, low_dzd=55000, high_dzd=65000, confidence="medium", kind="gpu")])
    db.commit()
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: {"ok": True, "data": {"prices": [], "note": "nothing"}, "sources": []})
    row = dz_market.lookup_key(db, settings, "gpu|rtx 4050|", "RTX 4050", "gpu", force=True)
    assert row is not None and row.ok and row.median_dzd == 60000 and "kept the price" in row.note
    fresh = dz_market.lookup_key(db, settings, "gpu|rtx 9999|", "RTX 9999", "gpu", force=True)
    assert fresh is None  # a product never priced stays unpriced


def test_one_price_per_card_model_but_vram_variants_stay_apart():
    assert pricebook.canonical(_card("RTX 3070"))[0] == pricebook.canonical(_card("RTX 3070 8 Go", vram=8))[0] == "gpu|rtx 3070|"
    a = Listing(subject="RTX 3060 12 Go", price_eur=200, specs={"gpu": "RTX 3060", "ram_gb": 12})
    b = Listing(subject="RTX 3060 8 Go", price_eur=200, specs={"gpu": "RTX 3060", "ram_gb": 8})
    assert pricebook.canonical(a)[0] == "gpu|rtx 3060|12" and pricebook.canonical(b)[0] == "gpu|rtx 3060|8"


def test_bundles_are_detected():
    assert pricebook.bundle_items("Carte graphique Rtx 3070 et une 3090") == ["RTX 3070", "RTX 3090"]
    assert pricebook.bundle_items("RTX 3060 + RTX 3070") == ["RTX 3060", "RTX 3070"]
    assert pricebook.bundle_items("Lot de 2 RTX 3060") == ["RTX 3060", "RTX 3060"]
    for single in ("MSI RTX 3070 Gaming X Trio 8 Go", "RTX 3060 12GB, 3 ventilateurs", "RTX 3070 / 1440p", "Rtx 3070 et 3070 ti"):
        assert pricebook.bundle_items(single) == [], single


def test_a_bundle_is_priced_as_the_sum_of_its_cards(monkeypatch):
    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    db.add(settings)
    db.commit()
    dz_market.set_manual_key(db, "gpu|rtx 3070|", "RTX 3070", "gpu", 86000)
    dz_market.set_manual_key(db, "gpu|rtx 3090|", "RTX 3090", "gpu", 200000)
    monkeypatch.setattr(dz_market, "_call_gemini", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    ad = _card("Carte graphique Rtx 3070 et une 3090")
    row = dz_market.lookup(db, settings, ad)
    assert row.median_dzd == 286000 and row.confidence == "low" and "RTX 3070" in row.note
    assert db.query(DzPrice).filter(DzPrice.cache_key.like("bundle|%")).count() == 0  # computed, not stored


def test_ads_follow_their_products_new_price(monkeypatch):
    db = _db()
    settings = Settings(id=1, llm_api_key="k", eur_dzd_parallel=280.0)
    search = Search(name="cards", gpu="rtx 3070", kind="gpu")
    ad = _card("MSI RTX 3070 Gaming")
    db.add_all([settings, search, ad])
    db.commit()
    db.add(SearchListing(search_id=search.id, listing_id=ad.id))
    db.add(DzPrice(cache_key="gpu|rtx 3070|", ok=True, median_dzd=75000, low_dzd=70000, high_dzd=80000, confidence="high", kind="gpu"))
    db.commit()
    enrich.fill_from_book(db, settings, [ad], search)
    assert ad.dz_price_median_dzd == 75000
    dz_market.set_manual_key(db, "gpu|rtx 3070|", "RTX 3070", "gpu", 88000)
    enrich.fill_from_book(db, settings, [ad], search)
    assert ad.dz_price_median_dzd == 88000 and ad.profit_ask_eur is not None


def test_unclear_laptops_are_read_by_the_spec_model_before_pricing(monkeypatch):
    from datetime import datetime, timedelta

    from app.extraction import llm

    db = _db()
    settings = Settings(id=1, llm_api_key="k")
    search = Search(name="laptops", cpu="i5 11400h")
    published = (datetime.utcnow() - timedelta(hours=2) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    ad = Listing(subject="PC portable ASUS TUF Gaming F15 16 Go", description="Processeur Intel onze, très bon état", price_eur=599.0, url="u", images=[],
                 specs={"ram_gb": 16, "gpu": "RTX 3060"}, first_publication_date=published, ship_ok="yes")
    db.add_all([settings, search, ad])
    db.commit()
    db.add(SearchListing(search_id=search.id, listing_id=ad.id))
    db.commit()
    read = []

    def fake_specs(db_, settings_, text, specs):
        read.append(text)
        return {"ok": True, "specs": {"cpu": "i5-11400h"}, "description": "Gaming laptop", "evidence": {"cpu": "i5 11e gen"}, "model": "m"}

    monkeypatch.setattr(llm, "extract_specs_detailed", fake_specs)
    asked = []
    monkeypatch.setattr(dz_market, "_call_gemini", lambda s, q, *a, **k: asked.append(q) or {
        "ok": True, "data": {"prices": [{"title": "laptop i5 11400H RTX 3060", "price_dzd": 150000, "condition": "used"}]}, "sources": []})

    assert pricebook.is_specific(dz_market.describe(ad)[0]) is False
    # a CPU named in the title is enough on its own, and makes it a computer rather than a bare card
    titled = Listing(subject="ASUS TUF F15 RTX 3060 i5 11e génération 16 Go", specs={"ram_gb": 16, "gpu": "RTX 3060"})
    assert dz_market.describe(titled)[0].startswith("laptop|i5g11|")
    enrich.run_for(db, settings, search, [ad])
    assert len(read) == 1 and ad.specs["cpu"] == "i5-11400h"
    assert asked and ad.dz_price_median_dzd == 150000
    enrich.run_for(db, settings, search, [ad])
    assert len(read) == 1  # each ad is read once
