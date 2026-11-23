"""Algerian market price lookup via Gemini 2.5 Flash-Lite on OpenRouter (web search).

For a laptop configuration we ask Gemini to search the web (Ouedkniss, retailers,
etc.) and return the going price in DZD. Results are cached per configuration so a
search run costs one lookup per distinct config, not one per listing.

Everything is best-effort: any failure returns ``None`` and the app falls back to the
European market median.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from ..config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from ..models import DzPrice, Listing, Settings
from . import pricebook

DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
TIMEOUT = 60.0
SUCCESS_TTL = timedelta(days=7)
FAILURE_TTL = timedelta(hours=6)
# Plausible range for a used laptop in Algeria, in DZD.
MIN_DZD = 15_000
MAX_DZD = 1_500_000


# The model can be free, but OpenRouter's web-search plugin is billed per result (~$0.007 a lookup),
# so lookups only happen on demand (see enrich.py) and the price book makes repeats free.
WEB_RESULTS = 3  # 3 results are enough for a median


def api_key(settings: Settings) -> str:
    # Same OpenRouter key as the rest of the app's LLM features.
    return (settings.llm_api_key or "").strip() or OPENROUTER_API_KEY


def available(settings: Settings) -> bool:
    return bool(getattr(settings, "dz_price_enabled", True) and api_key(settings))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def describe(listing: Listing) -> tuple[str, str]:
    """Return (cache_key, human description) for a listing, or ("", "") if too vague."""
    key, description, _kind = pricebook.canonical(listing)
    return key, description


def ad_context(listing: Listing) -> str:
    """Extra facts from the ad itself (title, condition, all extracted specs, description)."""
    specs = listing.specs or {}
    lines = []
    if listing.subject:
        lines.append(f"Ad title: {listing.subject[:200]}")
    condition = specs.get("condition") or listing.condition
    if condition:
        lines.append(f"Condition: {condition}")
    extra = {
        k: v
        for k, v in specs.items()
        if v not in (None, "", [], {}) and not k.endswith("confidence") and k != "condition"
    }
    if extra:
        lines.append("Extracted specs: " + ", ".join(f"{k}={v}" for k, v in extra.items())[:400])
    if listing.description:
        lines.append("Seller description: " + " ".join(listing.description.split())[:600])
    return "\n".join(lines)


PROMPT = (
    "Search the web for the current price in Algeria of this used (occasion) laptop: {query}.\n"
    "{context}\n"
    "Look at Algerian classifieds and shops (Ouedkniss first, then other Algerian sellers/"
    "retailers) and use real listings or shop prices in Algerian dinars (DZD / DA). "
    "Prefer USED prices; if you only find new prices, report them and lower your confidence.\n"
    "Ignore prices outside Algeria and ignore obvious outliers or accessories.\n"
    "Answer with ONLY this JSON, no prose, no markdown:\n"
    '{{"low_dzd": number|null, "median_dzd": number|null, "high_dzd": number|null, '
    '"samples": integer, "confidence": "high"|"medium"|"low", '
    '"basis": "used"|"new"|"mixed", "note": "one short sentence"}}\n'
    "Numbers are plain DZD amounts (e.g. 85000), not strings. Use null if you found nothing."
)


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = re.sub(r"[^\d.]", "", value.replace(",", "."))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if MIN_DZD <= number <= MAX_DZD else None


def _call_gemini(settings: Settings, query: str, context: str = "") -> dict[str, Any]:
    """Return {"ok": bool, "data": {...}, "sources": [...], "error": str}."""
    model = (getattr(settings, "gemini_model", "") or DEFAULT_MODEL).strip()
    if "/" not in model:
        model = f"google/{model}"
    model = model.removesuffix(":online")  # web search is requested through the plugin below, with a result cap
    body = {
        "model": model,
        "plugins": [{"id": "web", "max_results": WEB_RESULTS}],
        "messages": [{"role": "user", "content": PROMPT.format(query=query, context=context)}],
        "temperature": 0.1,
        "max_tokens": 3000,  # reasoning models spend tokens thinking before the JSON answer
        "reasoning": {"effort": "low"},
    }
    headers = {
        "Authorization": f"Bearer {api_key(settings)}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Laptop Deal Finder",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=body)
    except Exception as exc:  # network / timeout
        return {"ok": False, "error": f"request failed: {type(exc).__name__}"}

    if response.status_code != 200:
        try:
            message = response.json().get("error", {}).get("message", "")
        except Exception:
            message = ""
        if response.status_code == 401:
            from .keycheck import explain_401

            return {"ok": False, "error": "OpenRouter HTTP 401: " + explain_401(message)}
        return {"ok": False, "error": f"OpenRouter HTTP {response.status_code}: {message[:200]}"}

    try:
        message = response.json()["choices"][0]["message"]
        text = message.get("content") or ""
        annotations = message.get("annotations") or []
    except Exception:
        return {"ok": False, "error": "unreadable OpenRouter response"}

    data = _parse_json(text)
    if not data:
        return {"ok": False, "error": "model returned no JSON"}

    sources = []
    for item in annotations:
        cite = item.get("url_citation") or {}
        if cite.get("url"):
            sources.append({"title": cite.get("title") or "", "url": cite["url"]})
    return {"ok": True, "data": data, "sources": sources[:6]}


def _store(db: Session, key: str, query: str, result: dict[str, Any]) -> DzPrice:
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if row is None:
        row = DzPrice(cache_key=key)
        db.add(row)

    row.query = query
    row.fetched_at = _utcnow()
    row.low_dzd = row.median_dzd = row.high_dzd = None
    row.ok = False
    row.sources = []

    if not result.get("ok"):
        row.note = result.get("error", "lookup failed")
        row.confidence = "low"
    else:
        data = result["data"]
        median = _num(data.get("median_dzd"))
        low = _num(data.get("low_dzd"))
        high = _num(data.get("high_dzd"))
        if median is None and low is not None and high is not None:
            median = (low + high) / 2
        if median is None:
            row.note = (data.get("note") or "No Algerian prices found.")[:500]
            row.confidence = "low"
        else:
            low = min(low, median) if low is not None else median * 0.85
            high = max(high, median) if high is not None else median * 1.15
            row.low_dzd, row.median_dzd, row.high_dzd = round(low), round(median), round(high)
            confidence = str(data.get("confidence") or "low").lower()
            row.confidence = confidence if confidence in ("high", "medium", "low") else "low"
            basis = data.get("basis")
            note = data.get("note") or ""
            row.note = (f"[{basis}] {note}" if basis else note)[:500]
            row.sources = result.get("sources", [])
            row.ok = True
    db.commit()
    return row


def _book_row(db: Session, key: str) -> Optional[DzPrice]:
    """The price-book row for a product. A card ad with no stated VRAM shares the price of the same model
    (and the reverse); two different stated VRAM sizes, like RTX 3060 8 GB and 12 GB, stay separate."""
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if (row is not None and row.ok) or not key.startswith("gpu|"):
        return row
    _, name, vram = (key.split("|") + ["", ""])[:3]
    family = (
        db.query(DzPrice)
        .filter(DzPrice.cache_key.like(f"gpu|{name}|%"), DzPrice.ok.is_(True))
        .order_by(DzPrice.manual.desc(), DzPrice.fetched_at.desc())
        .all()
    )
    for candidate in family:
        other = (candidate.cache_key.split("|") + [""])[2]
        if not vram or not other or other == vram:
            return candidate
    return row


def lookup(db: Session, settings: Settings, listing: Listing, force: bool = False, allow_call: bool = True) -> Optional[DzPrice]:
    """Cached Algerian price row for the listing's configuration, or None.

    ``allow_call=False`` returns only what is already cached and never calls a model.
    """
    if not available(settings):
        return None
    key, query = describe(listing)
    if not key:
        return None

    row = _book_row(db, key)
    if row is not None and row.manual and row.ok:
        return row  # the user's own price always wins
    if not allow_call and key.startswith("laptop|") and not pricebook.is_specific(key):
        return None  # too vague to reuse another ad's price
    if row is not None and not force:
        age = _utcnow() - (row.fetched_at or _utcnow())
        if age < (SUCCESS_TTL if row.ok else FAILURE_TTL):
            return row if row.ok else None

    if not allow_call:
        return row if row is not None and row.ok else None  # book only: an older price beats no price

    # Coarse keys are shared by many ads, so only title-keyed (vague) lookups get this ad's own text.
    context = ad_context(listing) if key.startswith("title|") else ""
    row = _store(db, key, query, _call_gemini(settings, query, context))
    row.kind = pricebook.canonical(listing)[2]
    db.commit()
    return row if row.ok else None


def set_manual(db: Session, listing: Listing, median_dzd: float, low_dzd: Optional[float] = None, high_dzd: Optional[float] = None) -> DzPrice:
    """Store the user's own Algerian price for this listing's product key (overrides Gemini)."""
    key, query, kind = pricebook.canonical(listing)
    if not key:
        raise ValueError("This ad has too little information to build a price-book key.")
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if row is None:
        row = DzPrice(cache_key=key)
        db.add(row)
    row.query, row.kind = query, kind
    row.median_dzd = round(float(median_dzd))
    row.low_dzd = round(float(low_dzd)) if low_dzd else round(row.median_dzd * 0.9)
    row.high_dzd = round(float(high_dzd)) if high_dzd else round(row.median_dzd * 1.1)
    row.confidence, row.ok, row.manual, row.sources = "high", True, True, []
    row.note = "Entered manually"
    row.fetched_at = _utcnow()
    db.commit()
    return row


def last_error(db: Session, listing: Listing) -> str:
    key, _ = describe(listing)
    if not key:
        return "The ad has no usable title or specs to look up an Algerian price."
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    return (row.note if row and not row.ok else "") or ""
