from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..notify import telegram
from ..schemas import SettingsOut, SettingsUpdate
from .helpers import get_settings, mask_key

router = APIRouter(prefix="/api/settings", tags=["settings"])

COST_FIELDS = {
    "eur_dzd_parallel", "eur_dzd_official", "resale_haircut_pct", "avg_discount_pct", "customs_mode", "duty_rate",
    "solidarity_rate", "vat_rate", "personal_exemption_dzd", "personal_flat_threshold_dzd", "personal_flat_rate",
    "customs_fixed_fee_eur", "transfer_fee_eur", "porsay_tariff", "porsay_per_kg_over", "porsay_handling_eur",
    "default_packaging_kg", "laptop_weight_kg", "gpu_weight_kg", "laptop_box_cm", "gpu_box_cm",
}


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

    if isinstance(updates.get("porsay_tariff"), list):
        # Keep only well-formed tiers with the keys the shipping maths reads (max_kg, price_eur).
        tiers = []
        for tier in updates["porsay_tariff"]:
            if not isinstance(tier, dict):
                continue
            kg = tier.get("max_kg", tier.get("up_to_kg"))
            price = tier.get("price_eur")
            if kg is None or price is None:
                continue
            tiers.append({"max_kg": float(kg), "price_eur": float(price)})
        updates["porsay_tariff"] = tiers

    for field, value in updates.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    if COST_FIELDS & set(updates):
        from ..intelligence import verdict

        verdict.reprice_all(db, settings)
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


@router.post("/test/openrouter")
def test_openrouter(db: Session = Depends(get_db)) -> dict:
    """Run the real model calls with the saved key and say what is wrong."""
    from ..intelligence import dz_market, keycheck

    settings = get_settings(db)
    return keycheck.check_openrouter(
        dz_market.api_key(settings),
        model=(settings.verdict_model or "anthropic/claude-haiku-5.5"),
        search_model=(settings.gemini_model or "nvidia/nemotron-3-ultra-550b-a55b:free").replace(":online", ""),
        spec_model=(settings.spec_model or "inclusionai/ling-3.2-flash:free"),
    )


@router.post("/test/leboncoin")
def test_leboncoin() -> dict:
    """Fetch one real results page the way a scan does."""
    from ..scraping import leboncoin

    result = leboncoin.fetch_page(leboncoin.make_session(), "ordinateur portable", page=1)
    if result.blocked:
        return {"ok": False, "message": "Leboncoin blocked the request. Try again later or set a proxy.", "ads": 0}
    if result.error:
        return {"ok": False, "message": f"Fetch failed: {result.error}", "ads": 0}
    return {"ok": True, "message": f"Fetched a page with {len(result.ads)} ads.", "ads": len(result.ads)}
