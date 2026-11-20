"""Build French Leboncoin search queries from a stored search profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Search

DEFAULT_BASE = "pc portable"  # only used when the form has no inputs
CATEGORY_ID = "15"  # Leboncoin "Ordinateurs"; fixed for every search
VENDOR_TERMS = {
    "intel": "intel",
    "ryzen": "ryzen",
    "apple": "macbook",
    "snapdragon": "snapdragon",
}
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


def _spec_terms(search: Search, full: bool = True) -> list[str]:
    """Search words built only from what was entered in the form."""
    terms: list[str] = []
    if _clean(search.brand):
        terms.append(_clean(search.brand))
    if _clean(search.cpu):
        terms.append(_clean(search.cpu))
    elif _clean(search.cpu_family):
        family = _clean(search.cpu_family)
        terms.append(VENDOR_TERMS.get(family.lower(), family))
    if search.ram_min:
        terms.append(f"{int(search.ram_min)}go")
    if search.storage_min:
        terms.append(_storage_label(int(search.storage_min)))
    if full and _clean(search.gpu):
        terms.append(_clean(search.gpu))
    if full and search.screen_min:
        terms.append(f"{search.screen_min:g} pouces")
    if full and _clean(search.condition):
        terms.append(CONDITION_LABELS.get(search.condition.lower(), search.condition))
    return terms


def _params(search: Search) -> dict[str, Any]:
    params: dict[str, Any] = {"category": CATEGORY_ID}
    if search.price_min is not None or search.price_max is not None:
        params["price_min"] = search.price_min
        params["price_max"] = search.price_max
    return params


def generate_queries(search: Search, limit: int = 3) -> list[GeneratedQuery]:
    """Full query first, then a lighter one without GPU/screen/condition.

    With no inputs at all the text falls back to "pc portable" so the search is not empty.
    """
    params = _params(search)
    queries: list[GeneratedQuery] = []
    seen: set[str] = set()

    for full in (True, False):
        text = " ".join(" ".join(_spec_terms(search, full=full)).split()) or DEFAULT_BASE
        if text.lower() not in seen:
            seen.add(text.lower())
            queries.append(GeneratedQuery(text=text, params=dict(params)))

    return queries[:limit]
