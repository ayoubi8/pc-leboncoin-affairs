from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..notify import telegram
from ..schemas import SettingsOut, SettingsUpdate
from .helpers import get_settings, mask_key

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _out(settings) -> SettingsOut:
    data = SettingsOut.model_validate(settings)
    data.llm_key_set = bool((settings.llm_api_key or "").strip())
    data.llm_api_key = mask_key(settings.llm_api_key)
    data.telegram_token_set = bool((settings.telegram_bot_token or "").strip())
    data.telegram_bot_token = mask_key(settings.telegram_bot_token)
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

    if "telegram_bot_token" in updates:
        value = (updates.get("telegram_bot_token") or "").strip()
        if not value or "•" in value:
            updates.pop("telegram_bot_token", None)
        else:
            updates["telegram_bot_token"] = value

    for field, value in updates.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return _out(settings)


@router.post("/telegram/detect")
def telegram_detect(db: Session = Depends(get_db)) -> dict:
    """Find the chat id of whoever messaged the bot, and save it."""
    settings = get_settings(db)
    result = telegram.detect_chat(settings.telegram_bot_token)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    settings.telegram_chat_id = str(result["chat_id"])
    db.commit()
    return {"chat_id": settings.telegram_chat_id, "title": result.get("title", "")}


@router.post("/telegram/test")
def telegram_test(db: Session = Depends(get_db)) -> dict:
    settings = get_settings(db)
    result = telegram.send_test(settings)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}
