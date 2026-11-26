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
_temporary: dict[str, str] = {}  # product key -> why the last call failed for a reason that is not about the product
DEFAULT_DAILY_LOOKUPS = 30
CREDIT_FLAG_FOR = timedelta(hours=2)  # scans are hourly, so a real shortage keeps renewing this
_no_credit_at: Optional[datetime] = None


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
    "Find the prices people pay in Algeria for: {query}.\n"
    "Search with words like: {terms}\n"
    "{context}\n"
    "Use Algerian classifieds and shops (Ouedkniss, SSH Computer, Soom, other Algerian sellers), prices in Algerian "
    "dinars (DA / DZD). Ignore prices outside Algeria, accessories and parts.\n"
    "List EVERY individual price you saw, one entry per listing or shop product, even when they differ. "
    "Do not average them and do not leave any out: the median is computed from your list.\n"
    "Answer with ONLY this JSON, no prose, no markdown:\n"
    '{{"prices": [{{"title": "the listing or product title", "price_dzd": number, "condition": "used"|"new", '
    '"source": "site name"}}], "note": "one short sentence"}}\n'
    "price_dzd is a plain number like 86950, not a string. Use an empty list if you found nothing."
)

SUFFIXES = ("ti", "super", "xtx", "xt")
PARTS_WORDS = re.compile(r"pour pi[eè]ces|\bhs\b|en panne|for parts|ventilateur|backplate|water ?block|bo[iî]te vide", re.I)
LAPTOP_IN_TITLE = re.compile(r"portable|laptop|notebook|pc gamer|ordinateur", re.I)
OUTLIER_LOW, OUTLIER_HIGH = 0.6, 1.6


def search_terms(key: str, description: str) -> str:
    """Words that make web results show real Algerian listing prices."""
    if key.startswith("gpu|"):
        name = key.split("|")[1].upper()
        return f'"{name}" prix Algérie occasion DA ouedkniss · سعر {name} الجزائر'
    product = description.removeprefix("used laptop ").removeprefix("laptop/PC: ").removeprefix("graphics card: ")
    return f'"{product}" prix Algérie occasion DA ouedkniss'


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _same_card(title: str, name: str) -> bool:
    """True when a listing title is the same card as ``name`` ("rtx 3070"): a 3070 Ti or a laptop is not."""
    parts = name.lower().split()
    number = next((p for p in parts if p.isdigit()), "")
    wanted = parts[-1] if parts[-1] in SUFFIXES else ""
    if not number:
        return True
    found = re.search(rf"(?<!\d){number}(?!\d)\s*-?\s*(ti|super|xtx|xt)?\b", title, re.I)
    if found is None:
        return False
    return (found.group(1) or "").lower() == wanted and not LAPTOP_IN_TITLE.search(title)


def summarize(data: dict[str, Any], key: str = "") -> Optional[dict[str, Any]]:
    """Median and range from the prices the model listed, after dropping wrong variants and outliers.

    Falls back to the model's own median when it answered in the old format. None when nothing usable is left.
    """
    items = data.get("prices")
    if not isinstance(items, list):
        median = _num(data.get("median_dzd"))
        if median is None:
            return None
        low, high = _num(data.get("low_dzd")), _num(data.get("high_dzd"))
        confidence = str(data.get("confidence") or "low").lower()
        return {"median": median, "low": min(low or median * 0.85, median), "high": max(high or median * 1.15, median),
                "samples": int(data.get("samples") or 0), "confidence": confidence if confidence in ("high", "medium", "low") else "low",
                "basis": data.get("basis") or "", "dropped": 0}

    name = key.split("|")[1] if key.startswith("gpu|") else ""
    used: list[float] = []
    new: list[float] = []
    dropped = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        price = _num(item.get("price_dzd"))
        title = str(item.get("title") or "")
        if price is None or PARTS_WORDS.search(title) or (name and title and not _same_card(title, name)):
            dropped += 1
            continue
        (new if str(item.get("condition") or "").lower() == "new" else used).append(price)

    pool, basis = (used, "used") if len(used) >= 2 else (used + new, "new" if not used else "mixed")
    if not pool:
        return None
    middle = _median(pool)
    kept = [p for p in pool if OUTLIER_LOW * middle <= p <= OUTLIER_HIGH * middle]
    dropped += len(pool) - len(kept)
    median = _median(kept)
    confidence = "high" if len(kept) >= 4 else "medium" if len(kept) >= 2 else "low"
    if basis != "used" and confidence != "low":
        confidence = "medium" if confidence == "high" else "low"
    return {"median": median, "low": min(kept), "high": max(kept), "samples": len(kept), "confidence": confidence,
            "basis": basis, "dropped": dropped}


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


def _call_gemini(settings: Settings, query: str, context: str = "", terms: str = "") -> dict[str, Any]:
    """Return {"ok": bool, "data": {...}, "sources": [...], "error": str}."""
    model = (getattr(settings, "gemini_model", "") or DEFAULT_MODEL).strip()
    if "/" not in model:
        model = f"google/{model}"
    model = model.removesuffix(":online")  # web search is requested through the plugin below, with a result cap
    body = {
        "model": model,
        "plugins": [{"id": "web", "max_results": WEB_RESULTS}],
        "messages": [{"role": "user", "content": PROMPT.format(query=query, context=context, terms=terms or query)}],
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

    found = summarize(result["data"], key) if result.get("ok") else None
    if found is None and row.ok and row.median_dzd:
        # a re-check that finds nothing keeps the price we had: an empty web search says nothing about the product
        why = result.get("error") or (result.get("data") or {}).get("note") or "no price found"
        row.note = f"Last re-check found nothing ({str(why)[:120]}); kept the price from {row.fetched_at:%Y-%m-%d}."[:500]
        row.fetched_at = _utcnow()
        db.commit()
        return row

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
        if found is None:
            row.note = (data.get("note") or "No Algerian prices found.")[:500]
            row.confidence = "low"
        else:
            row.low_dzd, row.median_dzd, row.high_dzd = round(found["low"]), round(found["median"]), round(found["high"])
            row.confidence = found["confidence"]
            counted = f"{found['samples']} price(s) kept" + (f", {found['dropped']} dropped (other variant or outlier)" if found["dropped"] else "")
            basis = f"[{found['basis']}] " if found["basis"] else ""
            row.note = f"{basis}{counted}. {data.get('note') or ''}".strip()[:500]
            row.sources = result.get("sources", [])
            row.ok = True
    db.commit()
    return row


def _no_credit(error: str) -> bool:
    """OpenRouter says 402 when the account is empty and 403 "Key limit exceeded" when the key's own cap is used up."""
    return "HTTP 402" in error or ("HTTP 403" in error and "limit" in error.lower())


def _is_temporary(error: str) -> bool:
    return (
        error.startswith("request failed")
        or _no_credit(error)
        or any(f"HTTP {code}" in error for code in (408, 429, 500, 502, 503, 504))
    )


def _explain_temporary(error: str) -> str:
    if _no_credit(error):
        return "OpenRouter key is out of credit: raise its limit at openrouter.ai/keys"
    return error[:200]


def out_of_credit() -> bool:
    return _no_credit_at is not None and _utcnow() - _no_credit_at < CREDIT_FLAG_FOR


def lookups_today(db: Session) -> int:
    since = _utcnow() - timedelta(hours=24)
    return db.query(DzPrice).filter(DzPrice.manual.is_(False), DzPrice.fetched_at >= since).count()


def is_temporary_failure(listing: Listing) -> bool:
    return describe(listing)[0] in _temporary


def _book_row(db: Session, key: str) -> Optional[DzPrice]:
    """The price-book row for a product. A card ad with no stated VRAM shares the price of the same model
    (and the reverse); two different stated VRAM sizes, like RTX 3060 8 GB and 12 GB, stay separate."""
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if row is not None and row.ok:
        return row
    if key.startswith("laptop|") and pricebook.is_specific(key) and pricebook.is_estimate(key):
        # RAM unknown: the cheapest known configuration of this CPU, so the estimate never flatters the deal
        _, tier, _, _, gpu = (key.split("|") + [""] * 5)[:5]
        same_cpu = (
            db.query(DzPrice)
            .filter(DzPrice.cache_key.like(f"laptop|{tier}|%|{gpu}"), DzPrice.ok.is_(True), DzPrice.median_dzd.isnot(None))
            .order_by(DzPrice.median_dzd.asc())
            .first()
        )
        return same_cpu or row
    if not key.startswith("gpu|"):
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
    key, query, kind = pricebook.canonical(listing)
    if not key:
        return None
    if key.startswith("bundle|"):
        return _bundle(db, settings, key, query, force, allow_call)
    # Coarse keys are shared by many ads, so only title-keyed (vague) lookups get this ad's own text.
    context = ad_context(listing) if key.startswith("title|") else ""
    return lookup_key(db, settings, key, query, kind, context, force, allow_call)


def lookup_key(
    db: Session,
    settings: Settings,
    key: str,
    query: str,
    kind: str,
    context: str = "",
    force: bool = False,
    allow_call: bool = True,
) -> Optional[DzPrice]:
    """Price-book row for one product key, calling the model only when allowed and needed."""
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

    cap = int(getattr(settings, "dz_lookups_per_day", None) or DEFAULT_DAILY_LOOKUPS)
    if not force and lookups_today(db) >= cap:  # the Search price button (force) is your own decision
        _temporary[key] = f"Daily limit of {cap} price lookups reached; it continues tomorrow (Settings)."
        return row if row is not None and row.ok else None

    global _no_credit_at
    result = _call_gemini(settings, query, context, search_terms(key, query))
    if not result.get("ok") and _is_temporary(result.get("error", "")):
        # No credit, rate limit or network: say nothing about the product and never wipe a price we already have.
        _temporary[key] = _explain_temporary(result["error"])
        if _no_credit(result["error"]):
            _no_credit_at = _utcnow()
        return row if row is not None and row.ok else None
    _no_credit_at = None
    _temporary.pop(key, None)
    row = _store(db, key, query, result)
    row.kind = kind
    db.commit()
    return row if row.ok else None


def _bundle(db: Session, settings: Settings, key: str, query: str, force: bool, allow_call: bool) -> Optional[DzPrice]:
    """Several cards in one ad: your own price for the bundle, else the sum of each card's price (low confidence)."""
    own = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if own is not None and own.manual and own.ok:
        return own
    rows = []
    for name in key.removeprefix("bundle|").split("+"):
        part = lookup_key(db, settings, pricebook.gpu_key(name), f"used graphics card {name.upper()} (desktop GPU, bare card)",
                          "gpu", force=force, allow_call=allow_call)
        if part is None or not part.median_dzd:
            return None
        rows.append(part)
    total = DzPrice(cache_key=key, query=query, kind="gpu", ok=True, manual=False, confidence="low", sources=[])
    total.low_dzd = sum(r.low_dzd or r.median_dzd for r in rows)
    total.median_dzd = sum(r.median_dzd for r in rows)
    total.high_dzd = sum(r.high_dzd or r.median_dzd for r in rows)
    total.note = "Sum of " + " + ".join(f"{r.cache_key.split('|')[1].upper()} {r.median_dzd:,.0f} DA" for r in rows)
    return total


def set_manual_key(db: Session, key: str, query: str, kind: str, median_dzd: float) -> DzPrice:
    """Your own price for a product key (e.g. from /price in Telegram). The AI never overwrites it."""
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    if row is None:
        row = DzPrice(cache_key=key)
        db.add(row)
    row.query, row.kind = query, kind
    row.median_dzd = round(float(median_dzd))
    row.low_dzd, row.high_dzd = round(row.median_dzd * 0.9), round(row.median_dzd * 1.1)
    row.confidence, row.ok, row.manual, row.sources = "high", True, True, []
    row.note = "Entered manually"
    row.fetched_at = _utcnow()
    db.commit()
    return row


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
    if key in _temporary:
        return _temporary[key]
    row = db.query(DzPrice).filter(DzPrice.cache_key == key).first()
    return (row.note if row and not row.ok else "") or ""
