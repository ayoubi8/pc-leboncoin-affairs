"""Cheap, free checks that run BEFORE any paid lookup.

Reads the structured fields Leboncoin already gives us (sold/pending status, shippable, computer type,
old price) plus title wording, to drop junk early and flag risk. Nothing here calls an LLM.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import Listing

# hard junk: not a working machine / not the machine at all
BROKEN = re.compile(
    r"pour pi[eè]ces|pour piece|\bhs\b|en panne|ne s.?allume pas|ne d[ée]marre pas|ne boot|"
    r"[ée]cran (cass[ée]|fissur[ée]|hs)|carte m[eè]re (hs|morte|grill)|d[ée]fectueu|\bcass[ée]\b|"
    r"bloqu[ée] (icloud|bios|mot de passe)|icloud|mot de passe (bios|admin)|verrouill[ée]|"
    r"for parts|not working|dead",
    re.I,
)
ACCESSORY = re.compile(
    r"^\s*(chargeur|sacoche|housse|sac |batterie|clavier|souris|[ée]cran seul|dock|station d.accueil|"
    r"adaptateur|c[aâ]ble|ventilateur|coque|support|refroidisseur|ram |barrette|ssd |disque dur)\b",
    re.I,
)
# soft risk wording (kept, shown to the buyer)
SOFT_FLAGS = [
    (re.compile(r"sans (chargeur|alim)", re.I), "no charger"),
    (re.compile(r"sans (disque|ssd|hdd|ram|batterie)", re.I), "missing storage/RAM/battery"),
    (re.compile(r"touche[s]? (manquante|cass)|charni[eè]re|pixel|rayure|fissure|batterie (hs|us[ée]e|faible)", re.I), "cosmetic/battery wear"),
    (re.compile(r"qwerty|clavier (us|anglais)", re.I), "non-AZERTY keyboard (harder to resell)"),
    (re.compile(r"mining|minage|\bminer\b|ex[- ]?mining|rig\b", re.I), "possibly ex-mining GPU"),
    (re.compile(r"facture|garantie", re.I), "has invoice/warranty (positive)"),
]
PICKUP_ONLY = re.compile(r"main propre uniquement|remise en main propre|retrait (sur place|uniquement)|sur place uniquement|pas d.envoi|pas d.exp[ée]dition|non exp[ée]di", re.I)
SHIPS = re.compile(r"envoi possible|exp[ée]dition possible|je peux exp[ée]dier|livraison possible|mondial relay|colissimo|envoi (rapide|soign)", re.I)

SHIPPABLE_TYPES = {"mondial_relay", "shop2shop", "colissimo", "distance", "home_delivery", "chronopost"}


def attributes(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for attribute in (raw or {}).get("attributes") or []:
        key = attribute.get("key")
        if not key:
            continue
        value = attribute.get("value")
        if value in (None, ""):
            value = attribute.get("value_label")
        out[key] = "" if value is None else str(value)
    return out


def ship_signal(listing: Listing, attrs: dict[str, str]) -> str:
    """yes | no | unknown, from Leboncoin's own fields first, then the ad text."""
    shippable = attrs.get("shippable", "").lower()
    kind = attrs.get("shipping_type", "").lower()
    text = f"{listing.subject or ''} {listing.description or ''}"
    if PICKUP_ONLY.search(text):
        return "no"
    if shippable == "true" or kind in SHIPPABLE_TYPES:
        return "yes"
    if shippable == "false" or kind == "face_to_face":
        return "no"
    if SHIPS.search(text):
        return "yes"
    return "unknown"


def screen(listing: Listing) -> dict[str, Any]:
    """Return {"skip": bool, "reasons": [...], "flags": [...], "ship_ok": str, "old_price": float|None}."""
    attrs = attributes(listing.raw or {})
    title = listing.subject or ""
    text = f"{title} {listing.description or ''}"
    reasons: list[str] = []
    flags: list[str] = []

    status = attrs.get("transaction_status", "").lower()
    if status in ("sold", "pending"):
        reasons.append(f"Leboncoin marks it {status}")
    if (listing.raw or {}).get("status") not in (None, "", "active"):
        reasons.append(f"ad status {(listing.raw or {}).get('status')}")
    if BROKEN.search(title + " " + (listing.description or "")[:300]):
        reasons.append("broken / for parts")
    if ACCESSORY.search(title) and not (listing.specs or {}).get("cpu"):
        reasons.append("accessory, not a computer")
    ctype = attrs.get("computer_type", "")
    if ctype in ("desktop", "centralunit", "all_in_one"):
        flags.append(f"listed as {ctype} (not a laptop)")

    for pattern, label in SOFT_FLAGS:
        if pattern.search(text):
            flags.append(label)

    old_price = None
    try:
        old_price = float(attrs["old_price"]) if attrs.get("old_price") else None
    except ValueError:
        pass
    if old_price and listing.price_eur and old_price > listing.price_eur:
        flags.append(f"price dropped from {old_price:.0f} €")

    return {
        "skip": bool(reasons),
        "reasons": reasons,
        "flags": flags,
        "ship_ok": ship_signal(listing, attrs),
        "old_price": old_price,
    }


def scam_price(price: float | None, reference: float | None) -> bool:
    """True when the price is so far below the reference it is probably a scam or a broken item."""
    return bool(price and reference and price < 0.35 * reference)
