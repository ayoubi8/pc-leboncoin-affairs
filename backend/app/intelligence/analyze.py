from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..extraction import cpu_db, llm, specs as specs_mod
from ..logistics import landed
from ..models import Listing, Search, Settings
from . import deal, dz_market, freshness, market, match, pricebook, screen as screen_mod


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
    return pricebook.kind_of(listing)


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

    # Free checks first: sold/pending/broken/accessory ads never reach the paid Algerian lookup.
    checked = screen_mod.screen(listing)
    flags = list(checked["flags"])
    if screen_mod.scam_price(listing.price_eur, listing.market_median_eur) and (listing.market_samples or 0) >= 5:
        flags.append("suspiciously cheap (<35% of market)")
    listing.ship_ok = checked["ship_ok"]
    listing.screen_skip = "; ".join(checked["reasons"])[:200]
    if any("marks it sold" in r or "marks it pending" in r or r.startswith("ad status") for r in checked["reasons"]):
        listing.is_active = False
        listing.gone_at = listing.gone_at or now
    info = freshness.apply(listing, now)
    listing.risk_flags = flags + [f for f in info["flags"] if f not in flags]

    mismatch = match.hard_fail(search, listing) if search is not None else ""
    if listing.screen_skip or mismatch:  # no paid lookup for junk or for ads that do not fit this search
        listing.dz_price_low_dzd = listing.dz_price_median_dzd = listing.dz_price_high_dzd = None
        listing.dz_saving_pct = listing.dz_confidence = None
    else:
        apply_dz_comparison(db, settings, listing)  # cached per config; never forced here

    listing.last_analyzed_at = now


def apply_dz_comparison(
    db: Session,
    settings: Settings,
    listing: Listing,
    force: bool = False,
) -> None:
    """Landed cost (price + shipping + customs) in DZD vs. the Algerian market price.

    When a Gemini lookup succeeds, the deal score/label are driven by that comparison;
    otherwise they stay on the European-median score computed earlier.
    """
    if not listing.price_eur:
        return

    cost = landed.compute(settings, listing.price_eur, kind=_kind_for(listing), specs=listing.specs)
    listing.acquisition_score = deal.acquisition_score(cost["total_eur"], listing.market_median_eur)
    listing.dz_landed_dzd = round(cost["total_eur"] * float(settings.eur_dzd_parallel or 0), 0)

    row = dz_market.lookup(db, settings, listing, force=force)
    if row is None:
        listing.dz_price_low_dzd = listing.dz_price_median_dzd = listing.dz_price_high_dzd = None
        listing.dz_saving_pct = None
        listing.dz_confidence = None
        listing.dz_query = dz_market.describe(listing)[1]
        listing.dz_sources = []
        return

    listing.dz_price_low_dzd = row.low_dzd
    listing.dz_price_median_dzd = row.median_dzd
    listing.dz_price_high_dzd = row.high_dzd
    listing.dz_confidence = row.confidence
    listing.dz_query = row.query
    listing.dz_sources = row.sources or []
    listing.dz_saving_pct = deal.savings_pct(listing.dz_landed_dzd, row.median_dzd)

    score = deal.score_from_ratio(listing.dz_landed_dzd, row.median_dzd)
    if score is not None:
        listing.deal_score = score
        listing.deal_label = deal.classify(score)
