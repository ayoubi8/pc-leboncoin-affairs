from __future__ import annotations

from typing import Any, Optional

LABELS = ("excellent", "good", "fair", "overpriced")


def classify(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "fair"
    return "overpriced"


def score_from_ratio(price: Optional[float], median: Optional[float]) -> Optional[float]:
    if not price or not median or median <= 0:
        return None
    ratio = price / median
    score = 100 - (ratio - 0.80) * 200
    return round(max(0.0, min(100.0, score)), 1)


def acquisition_score(landed_eur: Optional[float], median: Optional[float]) -> Optional[float]:
    if not landed_eur or not median or median <= 0:
        return None
    score = 50 + (median - landed_eur) / median * 100
    return round(max(0.0, min(100.0, score)), 1)


def savings(price: Optional[float], median: Optional[float]) -> Optional[float]:
    if not price or not median:
        return None
    return round(median - price, 2)


def savings_pct(price: Optional[float], median: Optional[float]) -> Optional[float]:
    if not price or not median or median <= 0:
        return None
    return round((median - price) / median * 100, 1)


def payload(listing: Any) -> dict[str, Any]:
    return {
        "score": listing.deal_score,
        "label": listing.deal_label,
        "saving_eur": savings(listing.price_eur, listing.market_median_eur),
        "saving_pct": savings_pct(listing.price_eur, listing.market_median_eur),
        "acquisition_score": listing.acquisition_score,
        "match_score": listing.match_score,
    }
