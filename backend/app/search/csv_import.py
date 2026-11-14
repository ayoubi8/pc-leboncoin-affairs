from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from ..models import ImportBatch, Search, Settings
from .runner import upsert_ads

FIELD_ALIASES = {
    "list_id": {"list_id", "id", "ad_id"},
    "url": {"url", "link", "lien"},
    "subject": {"subject", "title", "titre", "titel"},
    "price": {"price", "prix", "price_eur"},
    "city": {"city", "ville", "location"},
    "zipcode": {"zipcode", "cp", "code_postal"},
    "department": {"department", "departement", "region"},
    "brand": {"brand", "marque"},
    "condition": {"condition", "etat", "état"},
    "description": {"description", "body", "texte"},
    "first_publication_date": {"first_publication_date", "date", "published_at"},
    "images": {"images", "image", "photos"},
    "category_id": {"category_id", "category", "categorie"},
}


def _resolve(row: dict[str, str], field: str) -> str:
    aliases = FIELD_ALIASES[field]
    for key, value in row.items():
        if key and key.strip().lower() in aliases:
            return (value or "").strip()
    return ""


def _parse_price(raw: str) -> tuple[Any, Any]:
    cleaned = (
        raw.lower()
        .replace("euros", "")
        .replace("eur", "")
        .replace("€", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace(",", ".")
        .strip()
    )
    if not cleaned:
        return None, None
    try:
        value = float(cleaned)
    except ValueError:
        return None, None
    if value <= 0:
        return None, None
    return int(round(value * 100)), value


def import_csv(
    db: Session,
    settings: Settings,
    search: Search,
    content: bytes,
    filename: str = "import.csv",
) -> ImportBatch:
    batch = ImportBatch(search_id=search.id, filename=filename, status="running")
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        text = content.decode("utf-8-sig", "replace")
        sample = text[:4096]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
    except Exception as exc:
        batch.status = "failed"
        batch.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        return batch

    ads: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        subject = _resolve(row, "subject")
        if not subject:
            errors.append(f"line {index}: missing subject/title")
            continue
        cents, price = _parse_price(_resolve(row, "price"))
        images = [
            part.strip() for part in _resolve(row, "images").replace("|", ",").split(",")
            if part.strip()
        ]
        ads.append(
            {
                "list_id": _resolve(row, "list_id") or None,
                "url": _resolve(row, "url"),
                "subject": subject,
                "price_cents": cents,
                "price_eur": price,
                "category_id": _resolve(row, "category_id"),
                "city": _resolve(row, "city"),
                "zipcode": _resolve(row, "zipcode"),
                "department": _resolve(row, "department"),
                "brand": _resolve(row, "brand"),
                "condition": _resolve(row, "condition"),
                "description": _resolve(row, "description"),
                "images": images,
                "first_publication_date": _resolve(row, "first_publication_date"),
                "is_boosted": False,
                "is_pro": False,
                "raw": {"source": "csv", "row": index},
            }
        )

    counts = upsert_ads(db, settings, search, None, ads)

    batch.rows_total = len(rows)
    batch.rows_imported = counts["new"] + counts["updated"]
    batch.rows_skipped = counts["skipped"] + len(errors)
    if errors:
        batch.status = "partial" if counts["touched"] else "failed"
    else:
        batch.status = "success"
    batch.error = "\n".join(errors[:50]) if errors else None
    db.commit()
    db.refresh(batch)

    batch._errors = errors  # type: ignore[attr-defined]
    return batch
