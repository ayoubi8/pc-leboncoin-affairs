from __future__ import annotations

from typing import Any, Optional

from ..models import Settings
from . import porsay


def estimate_package(settings: Settings, kind: str, specs: Optional[dict[str, Any]]) -> tuple[float, list[float]]:
    """Parcel weight/box from the item: the settings values are for a ~15.6" laptop; scale by screen size,
    and add a heavier charger/cooling allowance for gaming laptops."""
    packaging = float(settings.default_packaging_kg or 0)
    if kind == "gpu":
        return float(settings.gpu_weight_kg) + packaging, list(settings.gpu_box_cm or [])
    weight = float(settings.laptop_weight_kg)
    dims = [float(x) for x in (settings.laptop_box_cm or [])]
    screen = (specs or {}).get("screen_inches")
    if screen:
        factor_w, factor_d = (0.8, 0.93) if screen <= 14.5 else (1.3, 1.1) if screen >= 17 else (1.0, 1.0)
        weight *= factor_w
        dims = [round(x * factor_d, 1) for x in dims]
    gpu = str((specs or {}).get("gpu") or "").lower()
    if any(word in gpu for word in ("rtx", "gtx", "rx ")):
        weight += 0.5
    return weight + packaging, dims


def compute(
    settings: Settings,
    price_eur: float,
    kind: str = "laptop",
    weight_kg: Optional[float] = None,
    dims_cm: Optional[list[float]] = None,
    specs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    est_weight, est_dims = estimate_package(settings, kind, specs)
    if weight_kg is None:
        weight_kg = est_weight
    if dims_cm is None:
        dims_cm = est_dims

    shipping = porsay.quote(settings, weight_kg, dims_cm)
    transfer = float(getattr(settings, "transfer_fee_eur", 0) or 0)
    parallel = float(settings.eur_dzd_parallel or 0)

    total_eur = round(price_eur + shipping["total_eur"] + transfer, 2)  # parcels are received as gifts: no customs
    total_dzd = round(total_eur * parallel, 2)

    breakdown = [
        {"key": "purchase", "label": "Purchase price", "eur": round(price_eur, 2)},
        {"key": "porsay_shipping", "label": "Porsay shipping (France → Algeria)", "eur": shipping["total_eur"]},
        {"key": "porsay_handling", "label": "Porsay handling", "eur": shipping["handling_eur"]},
        {"key": "transfer", "label": "Transfer fee", "eur": round(transfer, 2)},
    ]
    for row in breakdown:
        row["dzd"] = round(row["eur"] * parallel, 2)

    return {
        "kind": kind,
        "price_eur": round(price_eur, 2),
        "shipping": shipping,
        "transfer_fee_eur": round(transfer, 2),
        "total_eur": total_eur,
        "total_dzd": total_dzd,
        "parallel_rate": parallel,
        "breakdown": breakdown,
    }
