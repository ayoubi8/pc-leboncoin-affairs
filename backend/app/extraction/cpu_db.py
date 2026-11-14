from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cpu_db.json"


@lru_cache(maxsize=1)
def _db() -> dict[str, Any]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_cpu(value: str) -> str:
    text = (value or "").lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"(i[3579])[\s\-]*(\d{4,5}[a-z]{0,2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    match = re.search(r"ryzen\s*([3579])\s*(\d{4}[a-z]{0,3})", text)
    if match:
        return f"ryzen {match.group(1)} {match.group(2)}"
    match = re.search(r"\b(?:apple\s+)?m([1-4])\s*(pro|max|ultra)?\b", text)
    if match:
        suffix = f" {match.group(2)}" if match.group(2) else ""
        return f"m{match.group(1)}{suffix}"
    match = re.search(r"\b(celeron|pentium|athlon)\s*([a-z]?\d{3,4})?", text)
    if match:
        return f"{match.group(1)} {match.group(2) or ''}".strip()
    match = re.search(r"\bn(\d{2,3})\b", text)
    if match:
        return f"n{match.group(1)}"
    return text.strip()


def family_of(cpu: str) -> str:
    normalized = normalize_cpu(cpu)
    if re.match(r"i[3579]-", normalized):
        return normalized[:2]
    match = re.match(r"ryzen\s*([3579])", normalized)
    if match:
        return f"ryzen{match.group(1)}"
    if normalized.startswith("m") and re.match(r"m[1-4]", normalized):
        return "apple_m"
    for name in ("celeron", "pentium", "athlon"):
        if normalized.startswith(name):
            return name
    return "unknown"


def lookup(cpu: str) -> Optional[dict[str, Any]]:
    normalized = normalize_cpu(cpu)
    if not normalized:
        return None
    for model in _db()["models"]:
        pattern = model["pattern"]
        if pattern in normalized or normalized in pattern:
            family = model["family"]
            return {
                "cpu": normalized,
                "family": family,
                "label": _db()["families"].get(family, {}).get("label", family),
                "score": model["score"],
            }
    family = family_of(normalized)
    if family != "unknown":
        base = _db()["families"].get(family, {}).get("base_score", 30)
        return {
            "cpu": normalized,
            "family": family,
            "label": _db()["families"].get(family, {}).get("label", family),
            "score": base,
        }
    return None


def score(cpu: str) -> int:
    info = lookup(cpu)
    return int(info["score"]) if info else 0


def label(cpu: str) -> str:
    info = lookup(cpu)
    return info["label"] if info else (cpu or "Unknown")
