from __future__ import annotations

from ..models import Settings


def rates(settings: Settings) -> dict[str, float]:
    return {
        "parallel": float(settings.eur_dzd_parallel or 0),
        "official": float(settings.eur_dzd_official or 0),
    }


def to_dzd(amount_eur: float, rate: float) -> float:
    return round(amount_eur * rate, 2)


def to_eur(amount_dzd: float, rate: float) -> float:
    return round(amount_dzd / rate, 2) if rate else 0.0


def convert(amount_eur: float, settings: Settings, use: str = "parallel") -> dict[str, float]:
    value = rates(settings)
    r = value["official"] if use == "official" else value["parallel"]
    return {"eur": round(amount_eur, 2), "dzd": to_dzd(amount_eur, r), "rate": r}
