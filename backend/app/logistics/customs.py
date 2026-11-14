from __future__ import annotations

from typing import Any, Optional

from ..models import Settings


def compute(
    settings: Settings,
    goods_eur: float,
    shipping_eur: float,
    mode: Optional[str] = None,
    declared_value_eur: Optional[float] = None,
) -> dict[str, Any]:
    """Algeria import charges on a CIF basis.

    ``personal`` follows the occasional-shipment relief (note 2723/25):
    ≤ exemption → 0, then a flat rate up to the second threshold, otherwise
    the standard regime. ``standard`` applies duty + solidarity + VAT.
    """
    active_mode = (mode or settings.customs_mode or "personal").lower()
    value_eur = float(declared_value_eur if declared_value_eur is not None else goods_eur)
    cif_eur = value_eur + float(shipping_eur or 0)
    official = float(settings.eur_dzd_official or 0)
    cif_dzd = cif_eur * official

    duty = solidarity = vat = flat = 0.0
    notes: list[str] = []
    effective_mode = active_mode

    if active_mode == "personal":
        exemption = float(settings.personal_exemption_dzd or 0)
        threshold = float(settings.personal_flat_threshold_dzd or 0)
        flat_rate = float(settings.personal_flat_rate or 0)
        if cif_dzd <= exemption:
            notes.append(
                f"Personal exemption: CIF {cif_dzd:,.0f} DZD ≤ {exemption:,.0f} DZD."
            )
        elif cif_dzd <= threshold:
            flat = cif_eur * flat_rate
            notes.append(
                f"Personal flat rate {flat_rate * 100:.0f}% applied "
                f"(CIF {cif_dzd:,.0f} DZD ≤ {threshold:,.0f} DZD)."
            )
        else:
            notes.append("Above the personal threshold: standard regime applied.")
            effective_mode = "standard"

    if effective_mode == "standard":
        duty = cif_eur * float(settings.duty_rate or 0)
        solidarity = cif_eur * float(settings.solidarity_rate or 0)
        vat = (cif_eur + duty + solidarity) * float(settings.vat_rate or 0)
        notes.append(
            "Standard regime: duty {:.0f}% + solidarity {:.0f}% + VAT {:.0f}% on CIF.".format(
                float(settings.duty_rate or 0) * 100,
                float(settings.solidarity_rate or 0) * 100,
                float(settings.vat_rate or 0) * 100,
            )
        )

    fixed = float(settings.customs_fixed_fee_eur or 0)
    total_eur = duty + solidarity + vat + flat + fixed

    return {
        "mode": effective_mode,
        "requested_mode": active_mode,
        "cif_eur": round(cif_eur, 2),
        "cif_dzd": round(cif_dzd, 2),
        "official_rate": official,
        "duty_eur": round(duty, 2),
        "solidarity_eur": round(solidarity, 2),
        "vat_eur": round(vat, 2),
        "flat_eur": round(flat, 2),
        "fixed_fee_eur": round(fixed, 2),
        "total_eur": round(total_eur, 2),
        "total_dzd": round(total_eur * official, 2),
        "effective_rate_pct": round(total_eur / cif_eur * 100, 1) if cif_eur else 0.0,
        "notes": notes,
    }
