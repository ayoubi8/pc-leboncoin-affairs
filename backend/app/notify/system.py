"""System health: is the scanner working, is the OpenRouter key valid? Alerts when it is not."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DzPrice, Run, Search, Settings
from . import telegram

BLOCKED_STREAK = 3
MIN_STALE_MINUTES = 120
REMIND_AFTER = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _interval_minutes(interval: str) -> int:
    from ..scheduler import INTERVAL_MINUTES

    return INTERVAL_MINUTES.get(interval, 24 * 60)


def _key_state(db: Session, settings: Settings) -> str:
    """'missing' | 'rejected' | 'ok' | 'unknown'."""
    from ..intelligence import dz_market

    if not dz_market.api_key(settings):
        return "missing"
    rows = db.execute(
        select(DzPrice).where(DzPrice.manual.is_(False)).order_by(DzPrice.fetched_at.desc()).limit(5)
    ).scalars().all()
    if not rows:
        return "unknown"
    if any(r.ok for r in rows):
        return "ok"
    if any(("401" in (r.note or "") or "User not found" in (r.note or "") or "No auth" in (r.note or "")) for r in rows):
        return "rejected"
    return "unknown"


def compute_health(db: Session, settings: Settings) -> dict[str, Any]:
    now = _now()
    runs = db.execute(select(Run).order_by(Run.id.desc()).limit(30)).scalars().all()
    streak = 0
    for run in runs:
        if run.status in ("blocked", "failed"):
            streak += 1
        elif run.status == "success":
            break
    last_success = next((r.finished_at for r in runs if r.status == "success" and r.finished_at), None)

    auto = db.execute(select(Search).where(Search.auto_check_enabled.is_(True))).scalars().all()
    expected = min((_interval_minutes(s.interval) for s in auto), default=None)
    age_min = (now - last_success).total_seconds() / 60 if last_success else None

    lookups = db.execute(
        select(DzPrice).where(DzPrice.manual.is_(False), DzPrice.fetched_at >= now - timedelta(hours=24))
    ).scalars().all()
    key = _key_state(db, settings)

    problems: list[dict[str, str]] = []
    if key in ("missing", "rejected"):
        problems.append({
            "kind": f"key_{key}", "severity": "error",
            "message": "No OpenRouter key saved." if key == "missing" else "OpenRouter rejected the API key (HTTP 401): no Algerian prices or verdicts until it is fixed.",
        })
    if streak >= BLOCKED_STREAK:
        problems.append({"kind": "scanner_blocked", "severity": "error", "message": f"The last {streak} scans were blocked or failed. Leboncoin may be blocking this IP."})
    if auto and settings.auto_check_enabled:
        stale_limit = max(MIN_STALE_MINUTES, 3 * (expected or 60))
        if age_min is None or age_min > stale_limit:
            problems.append({"kind": "scan_stale", "severity": "error", "message": "No successful scan for " + (f"{age_min / 60:.1f} h." if age_min is not None else "a long time.")})
    if settings.telegram_enabled and not (settings.telegram_chat_id or "").strip():
        problems.append({"kind": "telegram_no_chat", "severity": "warning", "message": "Telegram is enabled but no chat is linked yet."})

    return {
        "ok": not any(p["severity"] == "error" for p in problems),
        "problems": problems,
        "openrouter_key": key,
        "scan": {
            "last_success_at": last_success.isoformat() if last_success else None,
            "minutes_since_success": round(age_min) if age_min is not None else None,
            "blocked_streak": streak,
            "auto_searches": len(auto),
            "expected_interval_minutes": expected,
        },
        "dz_lookups_24h": {"ok": sum(1 for r in lookups if r.ok), "total": len(lookups)},
    }


def check_and_alert(db: Session, settings: Settings) -> list[str]:
    """Send one Telegram alert per new problem (reminder after 24 h); clear state when it resolves."""
    health = compute_health(db, settings)
    state = dict(settings.system_alert_state or {})
    now = _now()
    sent: list[str] = []
    active = {p["kind"] for p in health["problems"] if p["severity"] == "error"}

    for problem in health["problems"]:
        if problem["severity"] != "error":
            continue
        last = state.get(problem["kind"])
        if last and now - datetime.fromisoformat(last) < REMIND_AFTER:
            continue
        if settings.telegram_enabled and (settings.telegram_chat_id or "").strip():
            result = telegram.send_message(settings, f"🚨 <b>Deal Finder problem</b>\n{problem['message']}")
            if not result["ok"]:
                continue
        state[problem["kind"]] = now.isoformat()
        sent.append(problem["kind"])

    resolved = [k for k in state if k not in active]
    for kind in resolved:
        state.pop(kind)
        if settings.telegram_enabled and (settings.telegram_chat_id or "").strip():
            telegram.send_message(settings, f"✅ Resolved: {kind.replace('_', ' ')}")
    if sent or resolved:
        settings.system_alert_state = state
        db.commit()
    return sent
