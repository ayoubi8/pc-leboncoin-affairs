"""Honest AI verdict on a listing: resell margin in Algeria after all costs.

All the arithmetic is done here in Python (buy price after negotiation + shipping +
customs + fees, vs. the Algerian price found by Gemini). A small, cheap model
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
from . import dz_market, negotiation
from ..logistics import landed

DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
TIMEOUT = 60.0

# Margin (profit / total cost) thresholds that define a good deal.
GREAT_PCT = 30.0
GOOD_PCT = 15.0
FAIR_PCT = 5.0

SYSTEM = f"""You are a blunt, honest advisor for a reseller who buys used laptops/PC parts on Leboncoin (France) and sells them in Algeria.
You receive pre-computed numbers. NEVER recompute or invent figures; quote only the numbers given.

How the money works:
- Buy price = what the buyer expects to actually pay after negotiating (not always the asking price).
- Total cost = buy price + shipping France->Algeria + customs/taxes + transfer fees. Costs depend on the weight/box size.
- Algerian resale price = what Gemini found online for the same config in DZD; converted to EUR at the given parallel rate (1 EUR = rate DZD).
- Profit = Algerian resale price (EUR) - total cost (EUR). Margin = profit / total cost.

Definition of a good deal (margin on total cost):
- great: margin >= {GREAT_PCT:.0f}% and confidence is not low
- good: margin >= {GOOD_PCT:.0f}%
- fair: margin >= {FAIR_PCT:.0f}% (thin; only worth it if little effort/risk)
- skip: below {FAIR_PCT:.0f}% or negative, or the ad looks risky (parts/faulty, missing specs, very low-confidence Algerian price)

Be honest, not salesy. Lower the verdict if the Algerian price confidence is low, samples are few, specs are missing/uncertain, or the condition is bad. Mention the real risks (fake ad, missing charger, battery, customs surprises).

Answer with ONLY this JSON (no markdown):
{{"verdict": "great"|"good"|"fair"|"skip", "headline": "max 12 words", "opinion": "3-5 short sentences, plain English", "risks": ["short risk", ...], "max_buy_price_eur": number}}
max_buy_price_eur = the highest buy price that still leaves at least a {GOOD_PCT:.0f}% margin (you may round it; it must be consistent with the numbers given)."""


def apply(db, settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None) -> dict[str, Any]:
    """Generate the verdict and store it on the listing (fetching the Algerian price first if needed)."""
    from .analyze import apply_dz_comparison

    if not listing.dz_price_median_dzd:
        apply_dz_comparison(db, settings, listing)
    result = generate(settings, listing, buy_price_eur)  # raises ValueError without an Algerian price
    listing.ai_verdict = result
    listing.ai_verdict_label = result["verdict"]
    listing.ai_profit_eur = result["numbers"]["profit_eur"]
    db.commit()
    return result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _kind(listing: Listing) -> str:
    specs = listing.specs or {}
    if specs.get("gpu") and not specs.get("cpu") and not specs.get("ram_gb"):
        return "gpu"
    return "laptop"


def label_for(margin_pct: float, confidence: Optional[str]) -> str:
    if margin_pct >= GREAT_PCT and confidence != "low":
        return "great"
    if margin_pct >= GOOD_PCT:
        return "good"
    if margin_pct >= FAIR_PCT:
        return "fair"
    return "skip"


def compute_numbers(
    settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None
) -> Optional[dict[str, Any]]:
    """Deterministic profit maths. None when there is no price or no Algerian price."""
    ask = listing.price_eur
    if not ask or not listing.dz_price_median_dzd:
        return None

    recs = negotiation.recommendations(ask, listing.market_median_eur, listing.deal_label)
    buy = float(buy_price_eur) if buy_price_eur else float(recs["target_eur"] or ask)
    cost = landed.compute(settings, buy, kind=_kind(listing))
    rate = float(settings.eur_dzd_parallel or 280)

    resale_eur = listing.dz_price_median_dzd / rate
    profit_eur = resale_eur - cost["total_eur"]
    margin_pct = profit_eur / cost["total_eur"] * 100 if cost["total_eur"] else 0.0
    return {
        "ask_price_eur": round(ask, 2),
        "buy_price_eur": round(buy, 2),
        "negotiation_saving_eur": round(ask - buy, 2),
        "shipping_eur": cost["shipping"]["total_eur"],
        "customs_eur": cost["customs"]["total_eur"],
        "transfer_fee_eur": cost["transfer_fee_eur"],
        "total_cost_eur": cost["total_eur"],
        "total_cost_dzd": round(cost["total_eur"] * rate),
        "rate": rate,
        "dz_low_dzd": listing.dz_price_low_dzd,
        "dz_median_dzd": listing.dz_price_median_dzd,
        "dz_high_dzd": listing.dz_price_high_dzd,
        "dz_median_eur": round(resale_eur, 2),
        "dz_confidence": listing.dz_confidence,
        "profit_eur": round(profit_eur, 2),
        "profit_dzd": round(profit_eur * rate),
        "margin_pct": round(margin_pct, 1),
        "max_buy_for_good_eur": round(
            max(0.0, _max_buy(settings, listing, resale_eur, rate)), 2
        ),
    }


def _max_buy(settings: Settings, listing: Listing, resale_eur: float, rate: float) -> float:
    """Highest buy price keeping GOOD_PCT margin (bisection; costs are monotone in price)."""
    lo, hi = 0.0, float(listing.price_eur or 0) * 2 + 500
    for _ in range(30):
        mid = (lo + hi) / 2
        total = landed.compute(settings, mid, kind=_kind(listing))["total_eur"]
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
            f"it resells for about {numbers['dz_median_eur']} EUR in Algeria, a profit of "
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
        "max_tokens": 600,
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
    settings: Settings, listing: Listing, buy_price_eur: Optional[float] = None
) -> dict[str, Any]:
    """Build and return the verdict dict (also stored on the listing by the caller)."""
    numbers = compute_numbers(settings, listing, buy_price_eur)
    if numbers is None:
        raise ValueError("No Algerian price yet - run the Algerian price search first.")

    data = _ask_model(settings, listing, numbers)
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
