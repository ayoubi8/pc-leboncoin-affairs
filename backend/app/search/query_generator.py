"""Build French Leboncoin search queries from a stored search profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Search

DEFAULT_BASE = "pc portable"
CONDITION_LABELS = {
    "new": "neuf",
    "like_new": "comme neuf",
    "very_good": "très bon état",
    "good": "bon état",
    "fair": "état correct",
    "parts": "pour pièces",
}


@dataclass
class GeneratedQuery:
    text: str
    params: dict[str, Any] = field(default_factory=dict)


def _clean(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _storage_label(gb: int) -> str:
    if gb >= 1000 and gb % 1000 == 0:
        return f"{gb // 1000}to"
    return f"{gb}go"


def _base_terms(search: Search) -> list[str]:
    base = _clean(search.keyword) or DEFAULT_BASE
    terms = [base]
    if search.brand and search.brand.lower() not in base.lower():
        terms.append(f"{base} {search.brand}")
    return terms


def _spec_terms(search: Search, full: bool = True) -> list[str]:
    terms: list[str] = []
    if _clean(search.cpu):
        terms.append(_clean(search.cpu))
    elif _clean(search.cpu_family):
        terms.append(_clean(search.cpu_family))
    if search.ram_min:
        terms.append(f"{int(search.ram_min)}go")
    if search.storage_min:
        terms.append(_storage_label(int(search.storage_min)))
    if full and _clean(search.gpu):
        terms.append(_clean(search.gpu))
    if full and search.screen_min:
        screen = search.screen_min
        label = f"{screen:g}"
        terms.append(f"{label} pouces")
    if full and _clean(search.condition):
        label = CONDITION_LABELS.get(search.condition.lower(), search.condition)
        terms.append(label)
    return terms


def _params(search: Search) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if search.category:
        params["category"] = str(search.category)
    if search.price_min is not None or search.price_max is not None:
        params["price_min"] = search.price_min
        params["price_max"] = search.price_max
    if search.location:
        params["location"] = search.location
    return params


def generate_queries(search: Search, limit: int = 3) -> list[GeneratedQuery]:
    params = _params(search)
    queries: list[GeneratedQuery] = []
    seen: set[str] = set()

    for base in _base_terms(search):
        full = " ".join([base, *_spec_terms(search, full=True)]).strip()
        light = " ".join([base, *_spec_terms(search, full=False)]).strip()
        for text in (full, light):
            normalized = " ".join(text.split()).lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                queries.append(GeneratedQuery(text=" ".join(text.split()), params=dict(params)))
        if len(queries) >= limit:
            break

    return queries[:limit]
