from __future__ import annotations

from app.intelligence import screen
from app.models import Listing


def _l(subject="PC portable i5", description="", attrs=None, **kw):
    raw = {"status": "active", "attributes": [{"key": k, "value": v} for k, v in (attrs or {}).items()]}
    return Listing(subject=subject, description=description, raw=raw, specs=kw.pop("specs", {}), **kw)


def test_sold_pending_broken_and_accessories_are_skipped():
    assert screen.screen(_l(attrs={"transaction_status": "sold"}))["skip"]
    assert screen.screen(_l(attrs={"transaction_status": "pending"}))["skip"]
    assert screen.screen(_l("Dell XPS pour pièces"))["skip"]
    assert screen.screen(_l("Asus ROG écran cassé"))["skip"]
    assert screen.screen(_l("Chargeur Dell 65W"))["skip"]
    assert not screen.screen(_l("Dell XPS i7 16Go"))["skip"]
    assert not screen.screen(_l("Chargeur + PC Dell", specs={"cpu": "i7-1165g7"}))["skip"]


def test_ship_signal_uses_leboncoin_fields_then_text():
    assert screen.screen(_l(attrs={"shippable": "true", "shipping_type": "mondial_relay"}))["ship_ok"] == "yes"
    assert screen.screen(_l(attrs={"shippable": "false", "shipping_type": "face_to_face"}))["ship_ok"] == "no"
    assert screen.screen(_l(description="Remise en main propre uniquement"))["ship_ok"] == "no"
    assert screen.screen(_l(description="Envoi possible colissimo"))["ship_ok"] == "yes"
    assert screen.screen(_l())["ship_ok"] == "unknown"


def test_flags_and_price_drop_and_scam_price():
    result = screen.screen(_l("PC sans chargeur", attrs={"old_price": "700"}, price_eur=500.0))
    assert "no charger" in result["flags"] and any("dropped" in f for f in result["flags"])
    assert screen.scam_price(100, 600) and not screen.scam_price(400, 600) and not screen.scam_price(None, 600)
