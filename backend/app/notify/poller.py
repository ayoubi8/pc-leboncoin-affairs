"""Handle Telegram button presses and commands (contacted / bought / skip, /paid, /sold, /status)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..models import Listing, Settings
from . import deals, pipeline, system, telegram

ACTIONS = {"c": "contacted", "b": "bought", "s": "skipped"}
HELP = (
    "Commands:\n"
    "/deals - 5 newest fresh ads with price, profit and link\n"
    "/paid ID PRICE_EUR  - record what you paid\n"
    "/sold ID PRICE_DZD  - record what you sold it for\n"
    "/status - system health"
)


def _chat_ok(settings: Settings, chat: dict[str, Any]) -> bool:
    return str(chat.get("id")) == str(settings.telegram_chat_id).strip()


def _reply(settings: Settings, text: str) -> None:
    telegram.send_message(settings, text)


def _handle_callback(db: Session, settings: Settings, query: dict[str, Any]) -> None:
    data = query.get("data") or ""
    match = re.fullmatch(r"p:([cbs]):(\d+)", data)
    chat = (query.get("message") or {}).get("chat") or {}
    token = settings.telegram_bot_token
    if not match or not _chat_ok(settings, chat):
        telegram.answer_callback(token, query["id"], "Not allowed")
        return
    listing = db.get(Listing, int(match.group(2)))
    if listing is None:
        telegram.answer_callback(token, query["id"], "Ad not found")
        return
    status = ACTIONS[match.group(1)]
    pipeline.set_status(db, settings, listing, status)
    note = {"contacted": "Marked as contacted 📨", "bought": f"Marked as bought ✅ (≈{listing.bought_price_eur:.0f} €) - send /paid {listing.id} PRICE to correct it" if listing.bought_price_eur else "Marked as bought ✅", "skipped": "Skipped ⏭"}[status]
    telegram.answer_callback(token, query["id"], note)


def _handle_message(db: Session, settings: Settings, message: dict[str, Any]) -> None:
    if not _chat_ok(settings, message.get("chat") or {}):
        return
    text = (message.get("text") or "").strip()
    if text.startswith(("/start", "/help")):
        _reply(settings, HELP)
    elif text.startswith("/deals"):
        deals.send_top_deals(db, settings)
    elif text.startswith("/status"):
        health = system.compute_health(db, settings)
        lines = ["✅ All good" if health["ok"] else "🚨 Problems:"] + [f"• {p['message']}" for p in health["problems"]]
        scan = health["scan"]
        lines.append(f"Last good scan: {scan['minutes_since_success']} min ago" if scan["minutes_since_success"] is not None else "No successful scan yet")
        _reply(settings, "\n".join(lines))
    elif text.startswith(("/paid", "/sold")):
        parts = text.replace(",", ".").split()
        try:
            listing = db.get(Listing, int(parts[1]))
            value = float(parts[2])
        except (IndexError, ValueError):
            _reply(settings, "Usage: " + ("/paid ID PRICE_EUR" if text.startswith("/paid") else "/sold ID PRICE_DZD"))
            return
        if listing is None:
            _reply(settings, "Ad not found.")
            return
        if text.startswith("/paid"):
            pipeline.set_status(db, settings, listing, "bought", bought_price_eur=value)
            _reply(settings, f"Recorded: bought for {value:.0f} €.")
        else:
            pipeline.set_status(db, settings, listing, "sold", sold_price_dzd=value)
            outcome = pipeline.realised_profit(settings, listing)
            _reply(settings, f"Recorded: sold for {value:,.0f} DA." + (f" Realised profit {outcome['profit_eur']:+.0f} € ({outcome['margin_pct']}%)." if outcome else " Add /paid to see the profit."))


def process_updates(db: Session, settings: Settings) -> int:
    """Fetch and handle pending updates once. Returns how many were handled."""
    if not (settings.telegram_enabled and (settings.telegram_bot_token or "").strip() and (settings.telegram_chat_id or "").strip()):
        return 0
    result = telegram.get_updates(settings.telegram_bot_token, int(settings.telegram_update_offset or 0))
    if not result["ok"]:
        return 0
    handled = 0
    last_id = None
    for update in result["result"] or []:
        last_id = update["update_id"]
        try:
            if update.get("callback_query"):
                _handle_callback(db, settings, update["callback_query"])
            elif update.get("message"):
                _handle_message(db, settings, update["message"])
            handled += 1
        except Exception as exc:  # one bad update must not block the queue
            print(f"[telegram] update {last_id} failed: {type(exc).__name__}: {exc}")
    if last_id is not None:
        settings.telegram_update_offset = last_id + 1
        db.commit()
    return handled
