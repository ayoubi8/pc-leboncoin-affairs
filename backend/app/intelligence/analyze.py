from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..extraction import cpu_db, llm, specs as specs_mod
from ..logistics import landed
from ..models import Listing, Search, Settings
from . import deal, market, match


def _attributes(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in raw.get("attributes") or []:
        key = attribute.get("key")
        if not key:
            continue
        value = attribute.get("value")
        values = attribute.get("values")
        if value in (None, "") and isinstance(values, list) and values:
            value = values[0]
        if value not in (None, ""):
            result[key] = value
    return result


def _kind_for(listing: Listing) -> str:
    specs = listing.specs or {}
    if specs.get("gpu") and not specs.get("cpu") and not specs.get("ram_gb"):
        return "gpu"
    return "laptop"


def analyze_listing(
    db: Session,
    settings: Settings,
    listing: Listing,
    search: Optional[Search] = None,
    force: bool = False,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if force or not listing.specs:
        extracted, confidence, method = specs_mod.extract_specs(
            listing.subject or "",
            listing.description or "",
            _attributes(listing.raw or {}),
        )
    else:
        extracted = dict(listing.specs or {})
        confidence = dict(listing.spec_confidence or {})
        method = dict(listing.spec_method or {})

    missing = specs_mod.missing_fields(extracted)
    if missing and llm.available(settings):
        text = " ".join(part for part in (listing.subject, listing.description) if part)
        extra = llm.extract_specs_llm(db, settings, text[:4000], extracted)
        if extra:
            if extra.get("cpu") and not extracted.get("cpu"):
                extracted["cpu"] = str(extra["cpu"])
                extracted["cpu_family"] = cpu_db.family_of(extracted["cpu"])
                confidence["cpu"] = "medium"
                method["cpu"] = "llm"
            for field in ("ram_gb", "storage_gb", "screen_inches"):
                if extra.get(field) and not extracted.get(field):
                    try:
                        extracted[field] = int(float(extra[field])) if field != "screen_inches" else round(float(extra[field]), 1)
                    except (TypeError, ValueError):
                        continue
                    confidence[field] = "medium"
                    method[field] = "llm"
            for field in ("gpu", "brand", "condition"):
                if extra.get(field) and not extracted.get(field):
                    extracted[field] = str(extra[field])
                    confidence[field] = "medium"
                    method[field] = "llm"

    listing.specs = extracted
    listing.spec_confidence = confidence
    listing.spec_method = method
    listing.model_key = specs_mod.model_key(extracted)

    db.flush()

    market_info = market.compute_market(db, listing)
    listing.market_low_eur = market_info["low_eur"]
    listing.market_median_eur = market_info["median_eur"]
    listing.market_high_eur = market_info["high_eur"]
    listing.market_confidence = market_info["confidence"]
    listing.market_samples = market_info["samples"]

    listing.deal_score = deal.score_from_ratio(listing.price_eur, listing.market_median_eur)
    listing.deal_label = deal.classify(listing.deal_score)

    if search is not None:
        listing.match_score = match.compute_match(search, listing)["score"]

    if listing.price_eur:
        cost = landed.compute(settings, listing.price_eur, kind=_kind_for(listing))
        listing.acquisition_score = deal.acquisition_score(
            cost["total_eur"], listing.market_median_eur
        )

    listing.last_analyzed_at = now
