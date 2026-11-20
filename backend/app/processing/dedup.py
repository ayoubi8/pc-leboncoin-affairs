from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def fingerprint(ad: dict[str, Any]) -> str:
    subject = " ".join(normalize_text(ad.get("subject") or "").split())
    price = ad.get("price_eur")
    city = normalize_text(ad.get("city") or "").strip()
    return f"{subject}|{price}|{city}"


def listing_fingerprint(ad: dict[str, Any]) -> str:
    """Identity of an ad across re-posts: same title + same seller (or same city). Price is excluded on purpose."""
    subject = " ".join(normalize_text(ad.get("subject") or "").split())
    who = ad.get("seller_id") or normalize_text(ad.get("city") or "").strip()
    if not subject or not who:
        return ""
    return f"{subject}|{who}"[:300]


def dedupe_ads(ads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate within a single run: list_id, then URL, then fingerprint."""
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for ad in ads:
        list_id = ad.get("list_id")
        url = (ad.get("url") or "").split("?")[0].rstrip("/")
        key = f"id:{list_id}" if list_id else (f"url:{url}" if url else f"fp:{fingerprint(ad)}")

        if key not in by_key:
            by_key[key] = ad
            order.append(key)
            continue

        existing = by_key[key]
        # keep the more informative copy
        if _score(ad) > _score(existing):
            by_key[key] = _merge(existing, ad)

    return [by_key[key] for key in order]


def _score(ad: dict[str, Any]) -> int:
    score = 0
    if ad.get("price_eur"):
        score += 3
    if ad.get("description"):
        score += 2
    if ad.get("images"):
        score += 2
    if ad.get("brand"):
        score += 1
    if ad.get("url"):
        score += 1
    return score


def _merge(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            merged[key] = value
    return merged


def price_changed(previous: float | None, current: float | None) -> bool:
    if previous is None and current is None:
        return False
    if previous is None or current is None:
        return True
    return abs(previous - current) >= 0.01
