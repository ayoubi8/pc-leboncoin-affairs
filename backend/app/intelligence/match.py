from __future__ import annotations

import re
from typing import Any

from ..extraction import cpu_db
from ..models import Listing, Search

WEIGHTS = {
    "cpu": 0.22,
    "cpu_family": 0.08,
    "ram_min": 0.15,
    "storage_min": 0.15,
    "gpu": 0.20,
    "screen": 0.08,
    "brand": 0.06,
    "condition": 0.06,
}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _contains(haystack: str, needle: str) -> bool:
    haystack = _norm(haystack)
    needle = _norm(needle)
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True
    tokens = [token for token in needle.split() if len(token) > 1]
    return bool(tokens) and all(token in haystack for token in tokens)


def compute_match(search: Search, listing: Listing, include_missing: bool | None = None) -> dict[str, Any]:
    specs = listing.specs or {}
    include_missing = search.include_missing_specs if include_missing is None else include_missing
    unknown_value = 0.5 if include_missing else 0.0

    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, active: bool, known: bool, passed: bool, reason: str) -> None:
        if not active:
            return
        value = 1.0 if (known and passed) else (0.0 if known else unknown_value)
        status = "pass" if (known and passed) else ("fail" if known else "unknown")
        checks[name] = {"status": status, "value": value, "reason": reason}

    cpu = specs.get("cpu") or ""
    if _norm(search.cpu):
        known = bool(cpu)
        record("cpu", True, known, _contains(cpu or cpu_db.normalize_cpu(cpu), search.cpu),
               f"CPU {cpu or 'unknown'} vs {search.cpu}")
    if _norm(search.cpu_family):
        family = (specs.get("cpu_family") or cpu_db.family_of(cpu)) if cpu else ""
        known = bool(family) and family != "unknown"
        wanted = cpu_db.vendor_of(search.cpu_family)
        if wanted:  # vendor group: intel / ryzen / apple / snapdragon
            passed = cpu_db.vendor_of(family) == wanted
        else:  # legacy exact family value such as "i7"
            passed = _norm(family) == _norm(search.cpu_family)
        record("cpu_family", True, known, passed,
               f"family {family or 'unknown'} vs {search.cpu_family}")
    if search.ram_min:
        ram = specs.get("ram_gb")
        known = ram is not None
        record("ram_min", True, known, bool(ram and ram >= search.ram_min),
               f"RAM {ram or 'unknown'} vs >= {search.ram_min}")
    if search.storage_min:
        storage = specs.get("storage_gb")
        known = storage is not None
        record("storage_min", True, known, bool(storage and storage >= search.storage_min),
               f"storage {storage or 'unknown'} vs >= {search.storage_min}")
    if _norm(search.gpu):
        gpu = specs.get("gpu") or ""
        known = bool(gpu)
        record("gpu", True, known, _contains(gpu, search.gpu), f"GPU {gpu or 'unknown'} vs {search.gpu}")
    if search.screen_min or search.screen_max:
        screen = specs.get("screen_inches")
        known = screen is not None
        passed = known and (
            (not search.screen_min or screen >= search.screen_min)
            and (not search.screen_max or screen <= search.screen_max)
        )
        record("screen", True, known, bool(passed), f"screen {screen or 'unknown'}")
    if _norm(search.brand):
        brand = specs.get("brand") or listing.brand or ""
        known = bool(brand)
        record("brand", True, known, _contains(brand, search.brand), f"brand {brand or 'unknown'}")
    if _norm(search.condition):
        condition = specs.get("condition") or listing.condition or ""
        known = bool(condition)
        record("condition", True, known, _norm(condition) == _norm(search.condition),
               f"condition {condition or 'unknown'}")

    if not checks:
        score = 100.0
    else:
        total_weight = sum(WEIGHTS[name] for name in checks)
        score = sum(WEIGHTS[name] * check["value"] for name, check in checks.items()) / total_weight * 100

    return {"score": round(score, 1), "checks": checks}


HARD_CHECKS = ("cpu", "cpu_family", "gpu", "ram_min", "storage_min")


def hard_fail(search: Search, listing: Listing) -> str:
    """Why the ad does not fit the search's hard criteria (CPU/GPU/RAM/storage), or "" if it fits.

    A criterion the ad does not state only counts as a failure when the search excludes missing specs.
    """
    checks = compute_match(search, listing)["checks"]
    for name in HARD_CHECKS:
        check = checks.get(name)
        if check and (check["status"] == "fail" or (check["status"] == "unknown" and not search.include_missing_specs)):
            return check["reason"]
    return ""
