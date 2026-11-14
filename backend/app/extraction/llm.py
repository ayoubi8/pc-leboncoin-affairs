"""Optional OpenRouter LLM helpers (extraction fallback + negotiation text).

The app is fully functional without an LLM: every call here is best-effort and
returns ``None`` on any failure.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from ..config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from ..models import LlmCache, Settings

TIMEOUT = 60.0


def api_key(settings: Settings) -> str:
    return (settings.llm_api_key or "").strip() or OPENROUTER_API_KEY


def available(settings: Settings) -> bool:
    return bool(settings.llm_enabled and api_key(settings))


def _cache_get(db: Session, key: str) -> Optional[str]:
    row = db.query(LlmCache).filter(LlmCache.cache_key == key).first()
    return row.response if row else None


def _cache_put(db: Session, key: str, kind: str, response: str) -> None:
    if db.query(LlmCache).filter(LlmCache.cache_key == key).first():
        return
    db.add(LlmCache(cache_key=key, kind=kind, response=response))
    db.commit()


def _chat(
    db: Session,
    settings: Settings,
    kind: str,
    system: str,
    user: str,
    max_tokens: int = 700,
) -> Optional[str]:
    if not available(settings):
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    key = hashlib.sha256(
        json.dumps([kind, settings.llm_model, system, user], ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    cached = _cache_get(db, key)
    if cached is not None:
        return cached

    headers = {
        "Authorization": f"Bearer {api_key(settings)}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Laptop Deal Finder",
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
        if response.status_code != 200:
            return None
        data = response.json()
        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content") or ""
        ).strip()
    except Exception:
        return None

    if content:
        _cache_put(db, key, kind, content)
    return content or None


def _parse_json(content: str) -> Optional[dict[str, Any]]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


SPEC_SCHEMA = (
    'Return ONLY JSON: {"cpu": string|null, "ram_gb": int|null, '
    '"storage_gb": int|null, "gpu": string|null, "screen_inches": number|null, '
    '"brand": string|null, "condition": string|null}'
)


def extract_specs_llm(
    db: Session,
    settings: Settings,
    text: str,
    known: dict[str, Any],
) -> Optional[dict[str, Any]]:
    system = (
        "You extract laptop hardware specs from French second-hand marketplace ads. "
        "Never invent values; use null when the ad does not state a field. " + SPEC_SCHEMA
    )
    user = f"Known: {json.dumps(known, ensure_ascii=False)}\nAd:\n{text[:4000]}"
    content = _chat(db, settings, "extract_specs", system, user, max_tokens=400)
    if not content:
        return None
    parsed = _parse_json(content)
    if not parsed:
        return None
    return {k: v for k, v in parsed.items() if v not in (None, "")}


def negotiation_message(
    db: Session,
    settings: Settings,
    context: dict[str, Any],
    tone: str,
) -> Optional[str]:
    tone_fr = {
        "friendly": "poli, chaleureux et courtois",
        "direct": "direct et concis, sans détour",
        "firm": "ferme et professionnel, avec une limite claire",
    }.get(tone, "poli")
    system = (
        "Tu rédiges des messages de négociation en français pour Leboncoin. "
        "Le message doit être court (max 90 mots), naturel, sans emoji, "
        f"avec un ton {tone_fr}. Ne jamais mentionner que c'est généré par une IA. "
        "Donne seulement le message final, sans guillemets ni explication."
    )
    user = (
        "Annonce: {subject}\nPrix demandé: {ask} EUR\nOffre proposée: {offer} EUR\n"
        "Cible: {target} EUR\nÉtat/valeur: {note}\n"
    ).format(
        subject=context.get("subject", ""),
        ask=context.get("ask_price_eur", ""),
        offer=context.get("offer_price_eur", ""),
        target=context.get("target_price_eur", ""),
        note=context.get("note", ""),
    )
    return _chat(db, settings, "negotiation", system, user, max_tokens=350)
