"""Canonical product keys for the Algerian price book.

One Gemini lookup (or one manual price) should serve every ad of the "same" product, so keys are coarse:
CPU generation tier + RAM bucket + storage bucket + GPU class for laptops, GPU model (+VRAM) for cards.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..extraction import cpu_db
from ..models import Listing

RAM_STEPS = [4, 8, 12, 16, 24, 32, 48, 64, 128]
STORAGE_STEPS = [128, 256, 512, 1000, 2000, 4000]
DGPU_RE = re.compile(r"\b(rtx|gtx|rx)\s*(\d{3,4})\s*(ti|super|xt|m)?", re.I)


GEN_WORDS = re.compile(r"\bi([3579])[\s-]*(\d{1,2})\s*(?:th|st|nd|rd|e|[eè]me)?\s*g[eé]n", re.I)
MODEL_RE = re.compile(
    r"\b(latitude|inspiron|vostro|precision|xps|elitebook|probook|zbook|thinkpad|thinkbook|ideapad|yoga|legion|"
    r"vivobook|zenbook|expertbook|aspire|swift|nitro|predator|katana|cyborg|victus|omen|pavilion|envy)"
    r"\s+(?:1[3-7]\s+)?([a-z]{0,2}\d{2,4}[a-z]?)\b(?:\s+g(?:en)?\s*(\d{1,2})\b)?",
    re.I,
)


def title_cpu(title: str) -> str:
    """'Dell Latitude - i5 13 Gen' -> 'i5 13th gen', when the spec parser found no CPU."""
    match = GEN_WORDS.search(title or "")
    return f"i{match.group(1)} {int(match.group(2))}th gen" if match else ""


def model_name(title: str) -> str:
    """'Dell Latitude 5440 tres bon etat' -> 'latitude 5440'; "" when no laptop model is named."""
    match = MODEL_RE.search(title or "")
    if not match:
        return ""
    line, number, gen = match.group(1).lower(), match.group(2).lower(), match.group(3)
    return f"{line} {number}" + (f" g{int(gen)}" if gen else "")


def _bucket(value: Optional[float], steps: list[int], slack: float = 1.0) -> Optional[int]:
    if not value:
        return None
    chosen = None
    for step in steps:
        if step <= value * slack:
            chosen = step
    return chosen or steps[0]


def cpu_tier(cpu: str) -> str:
    """'i5-13420h' -> 'i5g13', 'ryzen 5 5600h' -> 'r5s5', 'm2 pro' -> 'm2 pro'."""
    normalized = cpu_db.normalize_cpu(cpu or "").lower()
    written = GEN_WORDS.search(normalized)
    if written:
        return f"i{written.group(1)}g{int(written.group(2))}"
    match = re.match(r"i([3579])-(\d{4,5})", normalized)
    if match:
        digits = match.group(2)
        # i5-13420H and i5-1335U are both 13th gen; i5-8250U is 8th. A 4-digit number starting with 1 is gen 10+.
        gen = int(digits[:2]) if len(digits) == 5 or digits[0] == "1" else int(digits[0])
        return f"i{match.group(1)}g{gen}"
    match = re.match(r"ryzen\s*([3579])\s*(\d)(\d{3})", normalized)
    if match:
        return f"r{match.group(1)}s{match.group(2)}"
    return normalized[:30]


LAPTOP_WORDS = re.compile(r"portable|laptop|notebook|pc|ordinateur|macbook|thinkpad|gamer|gaming pc|tour|unit[ée] centrale", re.I)


# a processor named in the title means a whole computer, not a bare card ("TUF F15 RTX 3060 i5 11e génération")
CPU_IN_TITLE = re.compile(r"\b(?:core\s*)?i[3579]\b|\bi[3579]-\d{4,5}|\bryzen\b|\b(?:celeron|pentium)\b", re.I)


def is_gpu_ad(specs: dict[str, Any], title: str = "") -> bool:
    """A bare graphics card ad: a dedicated GPU, no CPU, and no sign of a whole computer."""
    if not DGPU_RE.search(str(specs.get("gpu") or "")) or specs.get("cpu"):
        return False
    ram = specs.get("ram_gb")
    return (ram is None or ram <= 24) and not LAPTOP_WORDS.search(title or "") and not CPU_IN_TITLE.search(title or "")


def gpu_name(specs: dict[str, Any]) -> str:
    match = DGPU_RE.search(str(specs.get("gpu") or ""))
    if not match:
        return ""
    return " ".join(x for x in (match.group(1).upper(), match.group(2), (match.group(3) or "").upper()) if x)


# Cards sold with two VRAM sizes at clearly different prices keep the size in their key; every other model
# has one price, so "RTX 3070" and "RTX 3070 8 GB" share one price-book row.
MULTI_VRAM = {
    "gtx 1060", "rtx 2060", "rtx 3050", "rtx 3060", "rtx 3080", "rtx 4060 ti", "rtx 5060 ti",
    "rx 470", "rx 480", "rx 570", "rx 580", "rx 6500 xt", "rx 7600 xt", "rx 9060 xt",
}
VRAM_STEPS = [2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24]


def gpu_key(name: str, vram: Optional[float] = None) -> str:
    name = name.lower()
    size = _bucket(vram, VRAM_STEPS) if vram and name in MULTI_VRAM else None
    return f"gpu|{name}|{size or ''}"


# A second card in the same ad: "RTX 3070 et une 3090", "3060 + 3070", "lot de 2 RTX 3060".
_SERIES = {f"{a}{b}0" for a in ("10", "16", "20", "30", "40", "50") for b in range(5, 10)} | {
    str(n) for n in (470, 480, 570, 580, 590, 5500, 5600, 5700, 6400, 6500, 6600, 6650, 6700, 6750, 6800, 6900, 6950,
                     7600, 7700, 7800, 7900, 9060, 9070)
}
_EXTRA_CARD = re.compile(r"(?:\bet(?:\s+une?)?|\+|&|\bavec(?:\s+une?)?|,|/)\s*(?:(?:rtx|gtx|rx)\s*)?(\d{3,4})\b", re.I)
_LOT = re.compile(r"\blot\s+de\s+(\d)\b|\bx\s?([2-9])\b|\b([2-9])\s?x\s+(?:rtx|gtx|rx)", re.I)


def bundle_items(title: str) -> list[str]:
    """GPU models of an ad that sells several cards (["RTX 3070", "RTX 3090"]); [] for a single card."""
    title = title or ""
    found = [" ".join(x for x in (m.group(1).upper(), m.group(2), (m.group(3) or "").upper()) if x) for m in DGPU_RE.finditer(title)]
    if not found:
        return []
    family = found[0].split()[0]
    for match in _EXTRA_CARD.finditer(title):
        number = match.group(1)
        if number in _SERIES and not any(number in name.split() for name in found):
            found.append(f"{family} {number}")
    lot = _LOT.search(title)
    if lot and len(found) == 1:
        count = int(next(g for g in lot.groups() if g))
        found = found * min(count, 4)
    return found if len(found) >= 2 else []


def key_from_text(text: str) -> tuple[str, str, str]:
    """A product key typed by hand ("rtx 3070", "rtx 3060 12gb", "latitude 5440") -> (key, description, kind)."""
    match = DGPU_RE.search(text or "")
    if match:
        name = " ".join(x for x in (match.group(1).upper(), match.group(2), (match.group(3) or "").upper()) if x)
        vram = re.search(r"(\d{1,2})\s*(?:gb|go)\b", text, re.I)
        key = gpu_key(name, float(vram.group(1)) if vram else None)
        return key, f"used graphics card {name} (desktop GPU, bare card)", "gpu"
    model = model_name(text or "")
    if model:
        return f"model|{model}", f"used laptop {model}", "laptop"
    return "", "", ""


def canonical(listing: Listing) -> tuple[str, str, str]:
    """Return (key, description, kind); ("", "", "laptop") when there is too little to go on."""
    specs = listing.specs or {}
    brand = (specs.get("brand") or listing.brand or "").strip()
    cpu = (specs.get("cpu") or "").strip()
    ram = specs.get("ram_gb")
    storage = specs.get("storage_gb")
    screen = specs.get("screen_inches")

    if is_gpu_ad(specs, listing.subject or ""):
        items = bundle_items(listing.subject or "")
        if items:  # several cards: priced as the sum of each card's own price
            return "bundle|" + "+".join(sorted(i.lower() for i in items)), "bundle: " + " + ".join(items), "gpu"
        name = gpu_name(specs)
        if name:
            key = gpu_key(name, ram)
            size = key.rsplit("|", 1)[1]
            vram_txt = f" {size} GB" if size else ""
            return key, f"used graphics card {name}{vram_txt} (desktop GPU, bare card)", "gpu"

    cpu = cpu or title_cpu(listing.subject or "")
    if not cpu:
        model = model_name(listing.subject or "")
        if model:  # every ad of a named model shares one price
            name = f"{brand} {model}" if brand else model
            return f"model|{model}"[:200], f"used laptop {name}"[:300], "laptop"

    if not (cpu or ram or (brand and screen)):
        title = " ".join((listing.subject or "").split())[:120]
        gpu = (specs.get("gpu") or "").strip()
        if not (title and (brand or gpu or len(title) >= 8)):
            return "", "", "laptop"
        gpu_only = bool(gpu) and not cpu
        noun = "graphics card" if gpu_only else "laptop/PC"
        details = ", ".join(str(x) for x in (brand, gpu, f"{storage} GB storage" if storage else "") if x)
        return ("title|" + title.lower())[:200], (f"{noun}: {title}" + (f" ({details})" if details else ""))[:300], "gpu" if gpu_only else "laptop"

    tier = cpu_tier(cpu) if cpu else "?"
    ram_b = _bucket(ram, RAM_STEPS) if ram else None
    stor_b = _bucket(storage, STORAGE_STEPS, slack=1.08) if storage and ram_b else None  # no RAM: price by CPU alone
    gpu = gpu_name(specs)
    key = f"laptop|{tier}|{ram_b or '?'}|{stor_b or '?'}|{gpu.lower() if gpu else 'igpu'}"

    parts = []
    if cpu:
        parts.append(f"{cpu} ({tier})")
    if ram_b:
        parts.append(f"{ram_b} GB RAM")
    if stor_b:
        parts.append(f"{stor_b} GB SSD")
    if gpu:
        parts.append(gpu)
    return key[:200], ("used laptop " + ", ".join(parts))[:300], "laptop"


def is_specific(key: str) -> bool:
    """Can this key's price be reused for other ads? A card model or a named laptop model can, and so can a real
    CPU generation. "32 GB, CPU unknown" cannot: it also matches a pair of RAM sticks. Title keys belong to one ad."""
    if key.startswith(("gpu|", "model|", "bundle|")):
        return True
    if not key.startswith("laptop|"):
        return False
    tier = key.split("|")[1]
    return bool(re.fullmatch(r"i[3579]g\d+|r[3579]s\d|m[1-9].*", tier) or re.search(r"\d{4}", tier))


def is_estimate(key: str) -> bool:
    """The exact configuration is unknown (no RAM stated, or only a model name), so the price is low confidence."""
    return key.startswith(("model|", "bundle|")) or (key.startswith("laptop|") and key.split("|")[2] == "?")


def kind_of(listing: Listing) -> str:
    return "gpu" if is_gpu_ad(listing.specs or {}, listing.subject or "") else "laptop"
