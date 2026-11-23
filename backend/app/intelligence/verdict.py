"""Honest AI verdict on a listing: resell margin in Algeria after all costs.

All the arithmetic is done here in Python (buy price after negotiation + shipping +
fees, vs. the Algerian price found by Gemini). A small, cheap model
(Claude Haiku on OpenRouter) only writes the opinion from those numbers, so it
cannot invent figures. If the model is unavailable a rule-based verdict is returned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..config import OPENROUTER_BASE_URL
from ..models import Listing, Settings
from . import dz_market, negotiation, pricebook
from ..logistics import landed

DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
TIMEOUT = 60.0

# Margin (profit / total cost) thresholds that define a good deal.
GREAT_PCT = 30.0
GOOD_PCT = 15.0
FAIR_PCT = 5.0
TOO_CHEAP_RATIO = 0.30  # under 30 % of the Algerian value: a part, a fake price or a scam, not a bargain

SYSTEM = f"""You are a blunt, honest advisor for a reseller who buys used laptops/PC parts on Leboncoin (France) and sells them in Algeria.
You receive pre-computed numbers. NEVER recompute or invent figures; quote only the numbers given.

How the money works:
- Buy price = asking price minus the discount sellers typically accept (assumed_discount_pct); profit_ask_eur is the worst case if the seller refuses to negotiate.
- Total cost = buy price + shipping France->Algeria + transfer fees. There is no customs cost: parcels are received as gifts. Costs depend on the weight/box size.
- Algerian resale price = the median ASKING price found online for the same config in DZD, converted to EUR at the parallel rate (1 EUR = rate DZD), then reduced by resale_haircut_pct to a realistic selling price (dz_net_eur).
- Profit = dz_net_eur - total cost (EUR). Margin = profit / total cost. If profit_ask_eur is negative, say the deal only works if the seller negotiates.

Definition of a good deal (margin on total cost):
- great: margin >= {GREAT_PCT:.0f}% and confidence is not low
- good: margin >= {GOOD_PCT:.0f}%
- fair: margin >= {FAIR_PCT:.0f}% (thin; only worth it if little effort/risk)
- skip: below {FAIR_PCT:.0f}% or negative, or the ad looks risky (parts/faulty, missing specs, very low-confidence Algerian price)

Be honest, not salesy. Lower the verdict if the Algerian price confidence is low, samples are few, specs are missing/uncertain, or the condition is bad. Mention the real risks (fake ad, missing charger, battery).

Answer with ONLY this JSON (no markdown):
{{"verdict": "great"|"good"|"fair"|"skip", "headline": "max 12 words", "opinion": "3-5 short sentences, plain English", "risks": ["short risk", ...], "max_buy_price_eur": number}}
max_buy_price_eur = the highest buy price that still leaves at least a {GOOD_PCT:.0f}% margin (you may round it; it must be consistent with the numbers given)."""


def apply(db, settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None, use_ai: bool = True) -> dict[str, Any]:
    """Generate the verdict and store it on the listing (fetching the Algerian price first if needed).

    ``use_ai=False`` (Telegram alerts after a scan) writes the rule-based verdict and calls no model.
    """
    from .analyze import apply_dz_comparison

    if not listing.dz_price_median_dzd:
        apply_dz_comparison(db, settings, listing, allow_call=use_ai)
    result = generate(settings, listing, buy_price_eur, use_ai=use_ai)  # raises ValueError without an Algerian price
    listing.ai_verdict = result
    listing.ai_verdict_label = result["verdict"]
    listing.ai_profit_eur = result["numbers"]["profit_eur"]
    listing.profit_ask_eur = result["numbers"]["profit_ask_eur"]
    db.commit()
    return result


def apply_math(settings: Settings, listing: Listing) -> bool:
    """Profit and verdict from the stored Algerian price: no model call. Returns False without a price.

    A written AI verdict is kept while its numbers are still right; if the costs changed, its text would
    quote wrong figures, so the rule-based verdict replaces it.
    """
    if listing.screen_skip:
        clear_price(listing)
        return False
    numbers = compute_numbers(settings, listing)
    if numbers is None:
        return False
    if listing.price_eur < TOO_CHEAP_RATIO * numbers["dz_median_eur"]:
        clear_price(listing)
        flag = "suspiciously cheap for this product: check it is the real item"
        listing.risk_flags = list(listing.risk_flags or []) + ([] if flag in (listing.risk_flags or []) else [flag])
        return False
    stored = listing.ai_verdict or {}
    previous = (stored.get("numbers") or {}).get("profit_ask_eur")
    if stored.get("source") == "ai" and previous is not None and abs(previous - numbers["profit_ask_eur"]) < 1:
        listing.ai_profit_eur, listing.profit_ask_eur = numbers["profit_eur"], numbers["profit_ask_eur"]
        return True
    result = generate(settings, listing, use_ai=False)
    listing.ai_verdict = result
    listing.ai_verdict_label = result["verdict"]
    listing.ai_profit_eur = numbers["profit_eur"]
    listing.profit_ask_eur = numbers["profit_ask_eur"]
    return True


def clear_price(listing: Listing) -> None:
    """Remove a price and verdict that do not apply to this ad."""
    listing.dz_price_low_dzd = listing.dz_price_median_dzd = listing.dz_price_high_dzd = None
    listing.dz_saving_pct = listing.dz_confidence = None
    listing.ai_verdict = listing.ai_verdict_label = None
    listing.ai_profit_eur = listing.profit_ask_eur = None


def reprice_all(db, settings: Settings) -> int:
    """Recompute every priced ad after a cost setting changed. Free."""
    rows = db.query(Listing).filter(Listing.dz_price_median_dzd.isnot(None), Listing.price_eur.isnot(None)).all()
    done = sum(1 for listing in rows if apply_math(settings, listing))
    db.commit()
    return done


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _kind(listing: Listing) -> str:
    return pricebook.kind_of(listing)


def label_for(margin_pct: float, confidence: Optional[str]) -> str:
    if margin_pct >= GREAT_PCT and confidence != "low":
        return "great"
    if margin_pct >= GOOD_PCT:
        return "good"
    if margin_pct >= FAIR_PCT:
        return "fair"
    return "skip"


def _setting(settings: Settings, name: str, default: float) -> float:
    value = getattr(settings, name, None)
    return float(default if value is None else value)


def compute_numbers(
    settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None
) -> Optional[dict[str, Any]]:
    """Deterministic, conservative profit maths. None when there is no price or no Algerian price.

    - Resale: the Algerian median is an ASKING price, so a haircut (``resale_haircut_pct``) gives the
      price you can realistically get.
    - Buy price: the asking price minus the discount sellers really accept (``avg_discount_pct``), unless
      given explicitly. The profit at the full asking price is reported too (``profit_ask_eur``).
    """
    ask = listing.price_eur
    if not ask or not listing.dz_price_median_dzd:
        return None

    discount = max(0.0, min(40.0, _setting(settings, "avg_discount_pct", 6.0)))
    haircut = max(0.0, min(60.0, _setting(settings, "resale_haircut_pct", 10.0)))
    buy = float(buy_price_eur) if buy_price_eur else round(ask * (1 - discount / 100), 2)
    buy = min(buy, ask)
    kind = _kind(listing)
    cost = landed.compute(settings, buy, kind=kind, specs=listing.specs)
    cost_ask = cost if abs(buy - ask) < 0.005 else landed.compute(settings, ask, kind=kind, specs=listing.specs)
    rate = float(settings.eur_dzd_parallel or 280)

    resale_gross_eur = listing.dz_price_median_dzd / rate
    resale_eur = resale_gross_eur * (1 - haircut / 100)
    profit_eur = resale_eur - cost["total_eur"]
    profit_ask = resale_eur - cost_ask["total_eur"]
    margin_pct = profit_eur / cost["total_eur"] * 100 if cost["total_eur"] else 0.0
    margin_ask = profit_ask / cost_ask["total_eur"] * 100 if cost_ask["total_eur"] else 0.0
    return {
        "ask_price_eur": round(ask, 2),
        "buy_price_eur": round(buy, 2),
        "negotiation_saving_eur": round(ask - buy, 2),
        "assumed_discount_pct": round(discount, 1),
        "shipping_eur": cost["shipping"]["total_eur"],
        "transfer_fee_eur": cost["transfer_fee_eur"],
        "total_cost_eur": cost["total_eur"],
        "total_cost_dzd": round(cost["total_eur"] * rate),
        "rate": rate,
        "dz_low_dzd": listing.dz_price_low_dzd,
        "dz_median_dzd": listing.dz_price_median_dzd,
        "dz_high_dzd": listing.dz_price_high_dzd,
        "dz_median_eur": round(resale_gross_eur, 2),
        "resale_haircut_pct": round(haircut, 1),
        "dz_net_eur": round(resale_eur, 2),
        "dz_confidence": listing.dz_confidence,
        "profit_eur": round(profit_eur, 2),
        "profit_dzd": round(profit_eur * rate),
        "margin_pct": round(margin_pct, 1),
        "total_cost_ask_eur": cost_ask["total_eur"],
        "profit_ask_eur": round(profit_ask, 2),
        "margin_ask_pct": round(margin_ask, 1),
        "max_buy_for_good_eur": round(max(0.0, _max_buy(settings, listing, resale_eur, rate)), 2),
    }


def _max_buy(settings: Settings, listing: Listing, resale_eur: float, rate: float) -> float:
    """Highest buy price keeping GOOD_PCT margin (bisection; costs are monotone in price)."""
    lo, hi = 0.0, float(listing.price_eur or 0) * 2 + 500
    for _ in range(30):
        mid = (lo + hi) / 2
        total = landed.compute(settings, mid, kind=_kind(listing), specs=listing.specs)["total_eur"]
        if resale_eur - total >= total * GOOD_PCT / 100:
            lo = mid
        else:
            hi = mid
    return lo


def _fallback(numbers: dict[str, Any]) -> dict[str, Any]:
    verdict = label_for(numbers["margin_pct"], numbers["dz_confidence"])
    return {
        "verdict": verdict,
        "headline": f"{numbers['margin_pct']:.0f}% margin after all costs",
        "opinion": (
            f"Buying at {numbers['buy_price_eur']} EUR costs {numbers['total_cost_eur']} EUR landed; "
            f"it resells for about {numbers['dz_net_eur']} EUR in Algeria (after a {numbers['resale_haircut_pct']:.0f}% haircut), a profit of "
            f"{numbers['profit_eur']} EUR. (Rule-based verdict: AI opinion unavailable.)"
        ),
        "risks": [],
        "max_buy_price_eur": numbers["max_buy_for_good_eur"],
    }


def _ask_model(settings: Settings, listing: Listing, numbers: dict[str, Any]) -> Optional[dict[str, Any]]:
    model = (getattr(settings, "verdict_model", "") or DEFAULT_MODEL).strip()
    specs = listing.specs or {}
    user = json.dumps(
        {
            "title": listing.subject,
            "condition": specs.get("condition") or listing.condition,
            "specs": {k: v for k, v in specs.items() if v not in (None, "", [], {})},
            "description": " ".join((listing.description or "").split())[:700],
            "seller_is_pro": bool(listing.is_pro),
            "numbers": numbers,
            "algerian_price_note": listing.dz_query,
        },
        ensure_ascii=False,
    )
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": 1500,  # 600 was too tight: a longer opinion got cut off mid-JSON and counted as "no answer"
    }
    headers = {
        "Authorization": f"Bearer {dz_market.api_key(settings)}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Laptop Deal Finder",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=body)
        if response.status_code != 200:
            return None
        text = response.json()["choices"][0]["message"].get("content") or ""
    except Exception:
        return None
    data = dz_market._parse_json(text)
    if not data or data.get("verdict") not in ("great", "good", "fair", "skip"):
        return None
    return data


def generate(
    settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None, use_ai: bool = True
) -> dict[str, Any]:
    """Build and return the verdict dict (also stored on the listing by the caller)."""
    numbers = compute_numbers(settings, listing, buy_price_eur)
    if numbers is None:
        raise ValueError("No Algerian price yet - run the Algerian price search first.")

    data = _ask_model(settings, listing, numbers) if use_ai else None
    source = "ai"
    if data is None:
        data = _fallback(numbers)
        source = "rules"
    else:
        # The numbers are ground truth; never let the model move the verdict far from them.
        floor = label_for(numbers["margin_pct"], numbers["dz_confidence"])
        order = ["skip", "fair", "good", "great"]
        if order.index(data["verdict"]) > order.index(floor):
            data["verdict"] = floor

    risks = data.get("risks") or []
    return {
        "verdict": data["verdict"],
        "headline": str(data.get("headline") or "")[:160],
        "opinion": str(data.get("opinion") or "")[:1200],
        "risks": [str(r)[:160] for r in risks][:5] if isinstance(risks, list) else [],
        "max_buy_price_eur": data.get("max_buy_price_eur") or numbers["max_buy_for_good_eur"],
        "numbers": numbers,
        "source": source,
        "model": (getattr(settings, "verdict_model", "") or DEFAULT_MODEL) if source == "ai" else "rules",
        "generated_at": _utcnow().isoformat(),
    }
