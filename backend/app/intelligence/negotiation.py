from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..extraction import llm
from ..models import Listing, Settings

CONDITION_FR = {
    "new": "neuf",
    "like_new": "comme neuf",
    "very_good": "très bon état",
    "good": "bon état",
    "fair": "état correct",
    "parts": "pour pièces",
}


def _round5(value: float) -> float:
    return float(max(5, round(value / 5) * 5))


def recommendations(
    ask: Optional[float],
    market_median: Optional[float],
    deal_label: Optional[str] = None,
) -> dict[str, Any]:
    if not ask or ask <= 0:
        return {"ask_eur": ask, "offer_eur": None, "target_eur": None, "max_eur": None, "rationale": ""}

    reference = market_median if market_median else ask

    offer = min(ask * 0.88, reference * 0.85)
    offer = max(offer, ask * 0.65)
    target = min(ask * 0.95, reference * 0.92)
    maximum = min(ask, reference * 1.0 if market_median else ask * 0.97)

    offer = _round5(offer)
    target = _round5(max(target, offer + 5))
    maximum = _round5(max(maximum, target))
    if maximum > ask:
        maximum = _round5(ask)

    reasons = []
    if market_median:
        reasons.append(f"market median ≈ {market_median:.0f} €")
    if deal_label == "overpriced":
        reasons.append("listing is above market — negotiate harder")
    elif deal_label == "excellent":
        reasons.append("already a strong price — a light offer is enough")
    reasons.append("open low, settle near the market median, never pay above the asking price")

    return {
        "ask_eur": round(ask, 2),
        "offer_eur": offer,
        "target_eur": target,
        "max_eur": maximum,
        "rationale": "; ".join(reasons),
    }


def _template(tone: str, context: dict[str, Any]) -> str:
    subject = context.get("subject") or "article"
    offer = context.get("offer_price_eur")
    target = context.get("target_price_eur")
    maximum = context.get("max_price_eur")
    ask = context.get("ask_price_eur")
    note = (context.get("custom_note") or "").strip()
    condition = context.get("condition_fr") or context.get("condition") or ""

    condition_part = f" ({condition})" if condition else ""
    extra = f" {note}" if note else ""

    if tone == "direct":
        return (
            f"Bonjour, je vous propose {offer} € pour votre {subject}{condition_part}, "
            f"affiché à {ask} €.{extra} Je peux conclure rapidement et venir le chercher. "
            "Cordialement."
        )
    if tone == "firm":
        return (
            f"Bonjour, pour votre {subject}{condition_part}, mon offre est de {offer} € et "
            f"mon budget maximum est de {maximum} €.{extra} Je paie immédiatement et je me "
            "déplace sans délai. Si cela ne vous convient pas, je comprendrai et passerai à "
            "une autre annonce. Cordialement."
        )
    return (
        f"Bonjour, votre {subject}{condition_part} m'intéresse beaucoup. "
        f"Compte tenu de l'état et des prix actuels du marché, seriez-vous ouvert à {offer} € ?{extra} "
        f"Je peux me déplacer rapidement et régler directement. Merci et bonne journée."
    )


def build(
    db: Session,
    settings: Settings,
    listing: Listing,
    tone: str = "friendly",
    offer_override: Optional[float] = None,
    custom_note: str = "",
    use_ai: bool = True,
) -> dict[str, Any]:
    recs = recommendations(listing.price_eur, listing.market_median_eur, listing.deal_label)
    offer = offer_override if offer_override else recs["offer_eur"]

    context = {
        "subject": listing.subject,
        "ask_price_eur": listing.price_eur,
        "offer_price_eur": offer,
        "target_price_eur": recs["target_eur"],
        "max_price_eur": recs["max_eur"],
        "condition": (listing.specs or {}).get("condition") or listing.condition,
        "condition_fr": CONDITION_FR.get((listing.specs or {}).get("condition") or "", ""),
        "custom_note": custom_note,
        "note": recs["rationale"],
    }

    message: Optional[str] = None
    model = "template"
    if use_ai and llm.available(settings):
        generated = llm.negotiation_message(db, settings, context, tone)
        if generated:
            message = generated
            model = settings.llm_model
    if not message:
        message = _template(tone, context)

    return {
        "tone": tone,
        "ask_price_eur": listing.price_eur,
        "offer_price_eur": offer,
        "target_price_eur": recs["target_eur"],
        "max_price_eur": recs["max_eur"],
        "message_fr": message,
        "model": model,
        "rationale": recs["rationale"],
    }
