from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import SettingsOut, SettingsUpdate
from .helpers import get_settings, mask_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _out(settings) -> SettingsOut:
    data = SettingsOut.model_validate(settings)
    data.llm_key_set = bool((settings.llm_api_key or "").strip())
    data.llm_api_key = mask_key(settings.llm_api_key)
    return data


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return _out(get_settings(db))


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    settings = get_settings(db)
    updates = payload.model_dump(exclude_unset=True)

    if "llm_api_key" in updates:
        value = (updates.get("llm_api_key") or "").strip()
        if not value or "•" in value:
            updates.pop("llm_api_key", None)

    for field, value in updates.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return _out(settings)
