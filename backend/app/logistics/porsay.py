from __future__ import annotations

from typing import Any, Optional

from ..models import Settings


def volumetric_kg(dims_cm: Optional[list[float]]) -> Optional[float]:
    if not dims_cm or len(dims_cm) != 3:
        return None
    length, width, height = (float(v) for v in dims_cm)
    if length <= 0 or width <= 0 or height <= 0:
        return None
    return round(length * width * height / 5000.0, 3)


def _tariff(settings: Settings) -> list[dict[str, Any]]:
    tiers = settings.porsay_tariff or []
    return sorted(tiers, key=lambda tier: float(tier.get("max_kg", 0)))


def quote(
    settings: Settings,
    actual_kg: float,
    dims_cm: Optional[list[float]] = None,
) -> dict[str, Any]:
    volumetric = volumetric_kg(dims_cm)
    chargeable = max(float(actual_kg or 0), volumetric or 0)
    tiers = _tariff(settings)

    shipping = 0.0
    applied_tier: Optional[dict[str, Any]] = None
    if tiers:
        for tier in tiers:
            if chargeable <= float(tier.get("max_kg", 0)) + 1e-9:
                shipping = float(tier.get("price_eur", 0))
                applied_tier = tier
                break
        if applied_tier is None:
            last = tiers[-1]
            over = chargeable - float(last.get("max_kg", 0))
            shipping = float(last.get("price_eur", 0)) + max(0.0, over) * float(
                settings.porsay_per_kg_over or 0
            )
            applied_tier = last

    handling = float(settings.porsay_handling_eur or 0)
    total = round(shipping + handling, 2)
    return {
        "actual_kg": round(float(actual_kg or 0), 3),
        "volumetric_kg": volumetric,
        "chargeable_kg": round(chargeable, 3),
        "dimensions_cm": dims_cm,
        "shipping_eur": round(shipping, 2),
        "handling_eur": round(handling, 2),
        "total_eur": total,
        "tier_max_kg": (applied_tier or {}).get("max_kg"),
        "method": "max(actual, L×W×H/5000) + tier price",
    }
