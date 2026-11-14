from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Search
from ..schemas import ImportResult
from ..search.csv_import import import_csv
from .helpers import get_settings

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/searches/{search_id}/import-csv", response_model=ImportResult)
async def upload_csv(
    search_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportResult:
    search = db.get(Search, search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV too large (max 10 MB)")

    settings = get_settings(db)
    batch = import_csv(db, settings, search, content, filename=file.filename or "import.csv")

    return ImportResult(
        batch_id=batch.id,
        rows_total=batch.rows_total or 0,
        rows_imported=batch.rows_imported or 0,
        rows_skipped=batch.rows_skipped or 0,
        errors=getattr(batch, "_errors", [])[:20],
    )
