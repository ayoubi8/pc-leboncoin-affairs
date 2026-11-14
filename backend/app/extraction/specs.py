"""Extract hardware specs from a Leboncoin title/description/attributes.

Deterministic regex + structured attributes first; optional LLM fallback is
applied by the caller only when fields remain missing.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from . import cpu_db

BRANDS = [
    "apple", "macbook", "asus", "acer", "lenovo", "thinkpad", "ideapad", "hp",
    "dell", "msi", "samsung", "huawei", "honor", "xiaomi", "redmi", "gigabyte",
    "razer", "alienware", "microsoft", "surface", "toshiba", "chuwi", "infinit",
    "infinix", "tecno", "realme", "lg", "fujitsu", "packard", "clevo", "hasee",
]
BRAND_LABELS = {
    "apple": "Apple", "macbook": "Apple", "asus": "Asus", "acer": "Acer",
    "lenovo": "Lenovo", "thinkpad": "Lenovo", "ideapad": "Lenovo", "hp": "HP",
    "dell": "Dell", "msi": "MSI", "samsung": "Samsung", "huawei": "Huawei",
    "honor": "Honor", "xiaomi": "Xiaomi", "redmi": "Xiaomi", "gigabyte": "Gigabyte",
    "razer": "Razer", "alienware": "Alienware", "microsoft": "Microsoft",
    "surface": "Microsoft", "toshiba": "Toshiba", "chuwi": "Chuwi",
    "infinix": "Infinix", "tecno": "Tecno", "realme": "Realme", "lg": "LG",
    "fujitsu": "Fujitsu",
}
CONDITIONS = [
    (r"comme neuf|\bquasi neuf\b", "like_new"),
    (r"\bneuf\b|\bjamais servi\b|\bscell[eé]\b", "new"),
    (r"tr[eè]s bon [eé]tat|\bexcellent [eé]tat\b", "very_good"),
    (r"\bbon [eé]tat\b", "good"),
    (r"[eé]tat correct|\bcorrect\b", "fair"),
    (r"pour pi[eè]ces|\bhs\b|\ben panne\b|\bcass[eé]\b", "parts"),
]

CPU_PATTERNS = [
    re.compile(r"\b(?:intel\s+)?core\s+(i[3579])[\s\-]?(\d{4,5}[a-z]{0,2})\b", re.I),
    re.compile(r"\b(i[3579])[\s\-](\d{4,5}[a-z]{0,2})\b", re.I),
    re.compile(r"\bryzen\s+([3579])\s+(\d{4}[a-z]{0,3})\b", re.I),
    re.compile(r"\b(celeron|pentium|athlon)\s*([a-z]?\d{3,4})?\b", re.I),
    re.compile(r"\bn(\d{2,3})\b", re.I),
]
APPLE_CPU_RE = re.compile(r"(?<![\w.])(?:apple\s+)?m([1-4])(?:\s+(pro|max|ultra))?(?![\w.])", re.I)

SIZE_RE = re.compile(r"\b(\d{1,4})\s*(go|gb|to|tb)\b", re.I)
SCREEN_RE = re.compile(r"\b(\d{2}(?:[.,]\d)?)\s*(?:pouces?|\"|''|inch|in\b)", re.I)
SCREEN_BARE_RE = re.compile(r"(?<![\d.])(1[0-9][.,]\d)(?![\d.])")


def _attr(attributes: dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        for attribute_key, value in attributes.items():
            if attribute_key.lower() == key.lower() and value not in (None, ""):
                return value
    return None


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _find_cpu(text: str) -> Optional[tuple[str, str]]:
    for pattern in CPU_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        return cpu_db.normalize_cpu(match.group(0)), "regex"
    for match in APPLE_CPU_RE.finditer(text):
        start = max(0, match.start() - 8)
        context = text[start:match.start()].lower()
        if "ssd" in context or "nvme" in context or "." in context[-2:]:
            continue
        suffix = f" {match.group(2)}" if match.group(2) else ""
        return f"M{match.group(1)}{suffix}", "regex"
    return None


def _find_gpu(text: str) -> Optional[str]:
    match = re.search(r"\b(?:nvidia\s+)?(rtx|gtx)\s*(\d{3,4})\s*(ti|super)?\b", text, re.I)
    if match:
        name = f"{match.group(1).upper()} {match.group(2)}"
        if match.group(3):
            name += f" {match.group(3).upper()}"
        return name
    match = re.search(r"\b(?:amd\s+)?(?:radeon\s+)?rx\s*(\d{3,4})\s*(m|xt|gre)?\b", text, re.I)
    if match:
        name = f"RX {match.group(1)}"
        if match.group(2):
            name += match.group(2).upper()
        return name
    match = re.search(r"\b(iris\s+xe|iris\s+plus|iris|uhd\s+graphics|intel\s+hd\s+graphics)\b", text, re.I)
    if match:
        return " ".join(word.capitalize() for word in match.group(1).split())
    return None


def _find_screen(text: str) -> Optional[tuple[float, str]]:
    match = SCREEN_RE.search(text)
    if match:
        return float(match.group(1).replace(",", ".")), "high"
    match = SCREEN_BARE_RE.search(text)
    if match:
        return float(match.group(1).replace(",", ".")), "medium"
    return None


def _find_brand(text: str, attributes: dict[str, Any]) -> Optional[str]:
    explicit = _attr(attributes, "brand", "marque")
    if explicit:
        return str(explicit)
    lowered = text.lower()
    for token in BRANDS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return BRAND_LABELS.get(token, token.title())
    return None


def _find_condition(text: str, attributes: dict[str, Any]) -> Optional[str]:
    explicit = _attr(attributes, "condition", "item_condition", "etat")
    if explicit:
        mapped = str(explicit).lower()
        for pattern, label in CONDITIONS:
            if re.search(pattern, mapped, re.I):
                return label
        return mapped
    lowered = text.lower()
    for pattern, label in CONDITIONS:
        if re.search(pattern, lowered, re.I):
            return label
    return None


def _classify_sizes(text: str) -> tuple[Optional[int], Optional[int], dict[str, str]]:
    """Return (ram_gb, storage_gb, confidence_per_field)."""
    confidence: dict[str, str] = {}
    storages: list[tuple[int, int]] = []  # (value_gb, position)
    rams: list[tuple[int, int]] = []

    for match in SIZE_RE.finditer(text):
        value = int(match.group(1))
        unit = match.group(2).lower()
        gb = value * 1000 if unit in ("to", "tb") else value
        start, end = match.start(), match.end()
        context = text[max(0, start - 30):min(len(text), end + 30)].lower()

        if unit in ("to", "tb"):
            storages.append((gb, start))
            confidence["storage_gb"] = "high"
            continue
        if re.search(r"ssd|hdd|nvme|emmc|stockage|disque|storage", context):
            storages.append((gb, start))
            confidence["storage_gb"] = "high"
        elif re.search(r"ram|m[eé]moire|memoire|ddr", context):
            rams.append((gb, start))
            confidence["ram_gb"] = "high"
        elif gb >= 120 or gb in (1000, 2000):
            storages.append((gb, start))
            confidence.setdefault("storage_gb", "medium")
        else:
            rams.append((gb, start))
            confidence.setdefault("ram_gb", "medium")

    if not rams and storages:
        # a lone small value is likely RAM only if no explicit storage context
        pass
    if not storages and rams:
        # swap: overlapping RAM-like values are more likely storage when >= 120
        pass

    ram = max((v for v, _ in rams), default=None)
    storage = max((v for v, _ in storages), default=None)

    if ram is None and storage is not None and len(storages) >= 2:
        values = sorted({v for v, _ in storages})
        if values[0] < 128:
            ram = values[0]
            storage = values[-1]
            confidence["ram_gb"] = "low"
            confidence["storage_gb"] = "medium"

    return ram, storage, confidence


def extract_specs(
    title: str,
    description: str = "",
    attributes: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    attributes = attributes or {}
    text = " ".join(part for part in (title, description) if part)
    specs: dict[str, Any] = {}
    confidence: dict[str, str] = {}
    method: dict[str, str] = {}

    # CPU from structured attributes first
    cpu_attr = _attr(attributes, "cpu", "processor", "processeur")
    if cpu_attr:
        specs["cpu"] = cpu_db.normalize_cpu(str(cpu_attr))
        confidence["cpu"] = "high"
        method["cpu"] = "attribute"
    else:
        found = _find_cpu(title) or _find_cpu(description)
        if found:
            specs["cpu"] = cpu_db.normalize_cpu(found[0])
            confidence["cpu"] = "high"
            method["cpu"] = found[1]

    if specs.get("cpu"):
        specs["cpu_family"] = cpu_db.family_of(specs["cpu"])
        specs["cpu_label"] = cpu_db.label(specs["cpu"])
        specs["cpu_score"] = cpu_db.score(specs["cpu"])

    # RAM / storage
    ram_attr = _num(_attr(attributes, "ram", "memory", "memoire"))
    storage_attr = _num(_attr(attributes, "storage", "stockage", "disk", "disque"))
    if ram_attr:
        specs["ram_gb"] = int(ram_attr)
        confidence["ram_gb"] = "high"
        method["ram_gb"] = "attribute"
    if storage_attr:
        specs["storage_gb"] = int(storage_attr * 1000 if storage_attr <= 8 else storage_attr)
        confidence["storage_gb"] = "high"
        method["storage_gb"] = "attribute"

    ram, storage, size_conf = _classify_sizes(text)
    if "ram_gb" not in specs and ram:
        specs["ram_gb"] = int(ram)
        confidence.setdefault("ram_gb", size_conf.get("ram_gb", "medium"))
        method["ram_gb"] = "regex"
    if "storage_gb" not in specs and storage:
        specs["storage_gb"] = int(storage)
        confidence.setdefault("storage_gb", size_conf.get("storage_gb", "medium"))
        method["storage_gb"] = "regex"

    # GPU
    gpu_attr = _attr(attributes, "graphics_card", "gpu", "carte_graphique")
    if gpu_attr:
        specs["gpu"] = str(gpu_attr)
        confidence["gpu"] = "high"
        method["gpu"] = "attribute"
    else:
        gpu = _find_gpu(text)
        if gpu:
            specs["gpu"] = gpu
            confidence["gpu"] = "high"
            method["gpu"] = "regex"

    # screen
    screen_attr = _num(_attr(attributes, "screen_size", "ecran", "taille_ecran"))
    if screen_attr:
        specs["screen_inches"] = round(screen_attr, 1)
        confidence["screen_inches"] = "high"
        method["screen_inches"] = "attribute"
    else:
        screen = _find_screen(text)
        if screen:
            specs["screen_inches"], confidence["screen_inches"] = screen
            method["screen_inches"] = "regex"

    brand = _find_brand(text, attributes)
    if brand:
        specs["brand"] = brand
        confidence["brand"] = "high" if _attr(attributes, "brand", "marque") else "medium"
        method["brand"] = "attribute" if _attr(attributes, "brand", "marque") else "regex"

    condition = _find_condition(text, attributes)
    if condition:
        specs["condition"] = condition
        confidence["condition"] = "high" if _attr(attributes, "condition", "item_condition") else "medium"
        method["condition"] = "attribute" if _attr(attributes, "condition", "item_condition") else "regex"

    os_attr = _attr(attributes, "os", "operating_system", "systeme")
    if os_attr:
        specs["os"] = str(os_attr)
        confidence["os"] = "high"
        method["os"] = "attribute"

    return specs, confidence, method


def model_key(specs: dict[str, Any]) -> str:
    cpu = specs.get("cpu_family") or specs.get("cpu") or ""
    ram = specs.get("ram_gb") or ""
    storage = specs.get("storage_gb") or ""
    gpu = specs.get("gpu") or ""
    if cpu or ram:
        return f"{cpu}|{ram}|{storage}|{gpu}".lower()
    if specs.get("brand") and specs.get("screen_inches"):
        return f"{specs['brand']}|{specs.get('screen_inches')}|{storage}".lower()
    return ""


def missing_fields(specs: dict[str, Any]) -> list[str]:
    return [field for field in ("cpu", "ram_gb", "storage_gb") if not specs.get(field)]
