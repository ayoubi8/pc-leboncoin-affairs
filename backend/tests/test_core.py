from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.extraction import specs as specs_mod
from app.logistics import customs, landed, porsay
from app.main import app
from app.models import Listing, Settings


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def settings():
    init_db()
    with SessionLocal() as db:
        return db.get(Settings, 1)


def test_specs_gaming_laptop():
    specs, confidence, method = specs_mod.extract_specs(
        "PC portable ASUS TUF Gaming i5-13420H 16Go 512Go SSD RTX 3050 15.6 pouces",
        "Vends PC en trÃ¨s bon Ã©tat, chargeur inclus.",
    )
    assert specs["cpu"] == "i5-13420h"
    assert specs["cpu_family"] == "i5"
    assert specs["ram_gb"] == 16
    assert specs["storage_gb"] == 512
    assert specs["gpu"] == "RTX 3050"
    assert specs["screen_inches"] == 15.6
    assert specs["brand"] == "Asus"
    assert confidence["cpu"] == "high"
    assert method["cpu"] == "regex"


def test_specs_macbook():
    specs, _, _ = specs_mod.extract_specs("MacBook Air M2 8Go 256Go", "Comme neuf")
    assert specs["cpu"] == "m2"
    assert specs["cpu_family"] == "apple_m"
    assert specs["ram_gb"] == 8
    assert specs["storage_gb"] == 256
    assert specs["condition"] == "like_new"


def test_specs_storage_terabyte():
    specs, _, _ = specs_mod.extract_specs(
        "Dell i7 10750H 32 Go RAM 1To SSD 17.3",
        "Bon Ã©tat, batterie OK.",
    )
    assert specs["cpu"] == "i7-10750h"
    assert specs["ram_gb"] == 32
    assert specs["storage_gb"] == 1000
    assert specs["screen_inches"] == 17.3


def test_porsay_volumetric(settings):
    result = porsay.quote(settings, actual_kg=2.0, dims_cm=[40, 30, 8])
    assert result["volumetric_kg"] == pytest.approx(1.92)
    assert result["chargeable_kg"] == pytest.approx(2.0)
    assert result["total_eur"] > 0


def test_customs_far_below_exemption(settings):
    result = customs.compute(settings, goods_eur=150, shipping_eur=30, mode="personal")
    assert result["mode"] == "personal"
    assert result["total_eur"] == 0


def test_customs_flat_rate(settings):
    # CIF > 50,000 DZD but â‰¤ 100,000 DZD â†’ 30% flat
    result = customs.compute(settings, goods_eur=400, shipping_eur=50, mode="personal")
    assert result["mode"] == "personal"
    assert result["flat_eur"] > 0
    assert result["total_eur"] == pytest.approx(450 * 0.30, rel=1e-3)


def test_customs_standard(settings):
    result = customs.compute(settings, goods_eur=1000, shipping_eur=100, mode="standard")
    assert result["mode"] == "standard"
    assert result["duty_eur"] == pytest.approx(55, rel=1e-3)
    assert result["total_eur"] > result["duty_eur"]


def test_landed_cost(settings):
    result = landed.compute(settings, 500, kind="laptop")
    assert result["total_eur"] > 500
    assert result["total_dzd"] == pytest.approx(result["total_eur"] * settings.eur_dzd_parallel, rel=1e-3)
    assert len(result["breakdown"]) == 5


def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_api_search_lifecycle(client):
    created = client.post(
        "/api/searches",
        json={"name": "Test i5", "keyword": "pc portable", "cpu_family": "i5", "ram_min": 16},
    )
    assert created.status_code == 201, created.text
    search_id = created.json()["id"]

    listing = client.get(f"/api/searches/{search_id}")
    assert listing.status_code == 200

    preview = client.get(f"/api/searches/{search_id}/preview-queries")
    assert preview.status_code == 200
    assert preview.json()["queries"]

    results = client.get(f"/api/searches/{search_id}/results")
    assert results.status_code == 200
    assert results.json()["search_id"] == search_id

    patched = client.patch(f"/api/searches/{search_id}", json={"ram_min": 32})
    assert patched.status_code == 200
    assert patched.json()["ram_min"] == 32

    deleted = client.delete(f"/api/searches/{search_id}")
    assert deleted.status_code == 204


def test_api_settings_masks_key(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "\u2022" in data["llm_api_key"] or data["llm_api_key"] == ""

def test_leboncoin_detects_reader_captcha():
    from app.scraping.leboncoin import detect_block

    warning = "Warning: This page maybe requiring CAPTCHA, please make sure you are authorized"
    assert detect_block(200, warning) is True
    assert detect_block(200, "<html><body>normal</body></html>") is False
    assert detect_block(403, "") is True

def test_api_results_landed_sort(client):
    created = client.post("/api/searches", json={"name": "Landed", "keyword": "rtx 3060"})
    search_id = created.json()["id"]
    response = client.get(f"/api/searches/{search_id}/results?sort=landed_asc")
    assert response.status_code == 200
    assert response.json()["sort"] == "landed_asc"
    client.delete(f"/api/searches/{search_id}")

def test_csv_import_roundtrip(client):
    created = client.post(
        "/api/searches",
        json={"name": "CSV import", "keyword": "pc portable", "cpu_family": "i5"},
    )
    assert created.status_code == 201, created.text
    search_id = created.json()["id"]
    token = os.urandom(4).hex()

    csv_body = (
        "subject;price;city;brand;condition;url\n"
        f"PC portable Lenovo ThinkPad i5 16Go;450;Paris;Lenovo;tres bon etat;https://example.test/{token}/1\n"
        f"Dell Latitude i5 8Go;1 200 EUR;Lyon;Dell;neuf;https://example.test/{token}/2\n"
    ).encode("utf-8")

    imported = client.post(
        f"/api/searches/{search_id}/import-csv",
        files={"file": ("ads.csv", csv_body, "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["rows_total"] == 2
    assert payload["rows_imported"] == 2
    assert payload["errors"] == []

    results = client.get(f"/api/searches/{search_id}/results", params={"sort": "price_asc"})
    assert results.status_code == 200
    items = results.json()["items"]
    assert len(items) == 2
    prices = [item["price_eur"] for item in items]
    assert prices == [450.0, 1200.0]

    first_id = items[0]["id"]
    detail = client.get(f"/api/listings/{first_id}")
    assert detail.status_code == 200
    assert detail.json()["subject"].startswith("PC portable")

    quote = client.post(
        f"/api/listings/{first_id}/quote",
        json={"offer_price_eur": 400, "kind": "laptop"},
    )
    assert quote.status_code == 200
    assert quote.json()["landed_cost"]["total_eur"] > 0

    client.delete(f"/api/searches/{search_id}")

