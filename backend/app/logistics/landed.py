from __future__ import annotations

from typing import Any, Optional

from ..models import Settings
from . import customs, porsay


def compute(
    settings: Settings,
    price_eur: float,
    kind: str = "laptop",
    weight_kg: Optional[float] = None,
    dims_cm: Optional[list[float]] = None,
) -> dict[str, Any]:
    packaging = float(settings.default_packaging_kg or 0)
    if weight_kg is None:
        base_weight = float(
            settings.gpu_weight_kg if kind == "gpu" else settings.laptop_weight_kg
        )
        weight_kg = base_weight + packaging
    if dims_cm is None:
        dims_cm = list(settings.gpu_box_cm if kind == "gpu" else settings.laptop_box_cm or [])

    shipping = porsay.quote(settings, weight_kg, dims_cm)
    charges = customs.compute(
        settings,
        goods_eur=price_eur,
        shipping_eur=shipping["total_eur"],
    )
    transfer = float(getattr(settings, "transfer_fee_eur", 0) or 0)
    parallel = float(settings.eur_dzd_parallel or 0)

    total_eur = round(price_eur + shipping["total_eur"] + charges["total_eur"] + transfer, 2)
    total_dzd = round(total_eur * parallel, 2)

    breakdown = [
        {"key": "purchase", "label": "Purchase price", "eur": round(price_eur, 2)},
        {"key": "porsay_shipping", "label": "Porsay shipping (France → Algeria)", "eur": shipping["total_eur"]},
        {"key": "porsay_handling", "label": "Porsay handling", "eur": shipping["handling_eur"]},
        {"key": "customs", "label": "Customs & taxes", "eur": charges["total_eur"]},
        {"key": "transfer", "label": "Transfer fee", "eur": round(transfer, 2)},
    ]
    for row in breakdown:
        row["dzd"] = round(row["eur"] * parallel, 2)

    return {
        "kind": kind,
        "price_eur": round(price_eur, 2),
        "shipping": shipping,
        "customs": charges,
        "transfer_fee_eur": round(transfer, 2),
        "total_eur": total_eur,
        "total_dzd": total_dzd,
        "parallel_rate": parallel,
        "breakdown": breakdown,
    }
