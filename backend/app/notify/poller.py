"""Handle Telegram button presses and commands (/deals browser, contacted / bought / skip, /paid, /sold, /price, /status)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..models import Listing, Settings
from . import browser, deals, pipeline, system, telegram

ACTIONS = {"c": "contacted", "b": "bought", "s": "skipped"}
NOTES = {"contacted": "Marked as contacted 📨", "bought": "Marked as bought ✅", "skipped": "Skipped ⏭", "": "Undone"}
HELP = (
    "Commands:\n"
    "/deals - your searches; tap one to go through its best deals one by one\n"
    "/best - the best deals of all searches\n"
    "/price rtx 3070 88000 - set a product's Algerian price yourself (the AI never overwrites it)\n"
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
    message = query.get("message") or {}
    chat = message.get("chat") or {}
    token = settings.telegram_bot_token
    if not _chat_ok(settings, chat):
        telegram.answer_callback(token, query["id"], "Not allowed")
        return

    alert = re.fullmatch(r"p:([cbs]):(\d+)|u:(\d+)", data)
    if alert:  # buttons under an alert message
        listing = db.get(Listing, int(alert.group(2) or alert.group(3)))
        status = ACTIONS[alert.group(1)] if alert.group(1) else ""
        telegram.answer_callback(token, query["id"], "Ad not found" if listing is None else NOTES[status])  # stop the spinner first
        if listing is None:
            return
        pipeline.set_status(db, settings, listing, status)
        if message.get("message_id"):
            telegram.edit_buttons(settings, int(message["message_id"]), deals.alert_buttons(listing))
        return

    # browser buttons change the card in well under a second (updates arrive by long polling), then the tap is answered
    try:
        note = browser.handle(db, settings, data, message)
    except Exception as exc:
        db.rollback()
        print(f"[telegram] button {data!r} failed: {type(exc).__name__}: {exc}")
        note = "Something went wrong, send /deals again"
    telegram.answer_callback(token, query["id"], note)


def _set_price(db: Session, settings: Settings, text: str) -> None:
    from ..intelligence import dz_market, enrich, pricebook
    from ..models import Search

    match = re.fullmatch(r"/price(?:@\w+)?\s+(.+)\s+(\d[\d.,]*)\s*(?:da|dzd)?", text.strip(), re.I)  # the price is the last number
    if not match:
        _reply(settings, "Usage: /price PRODUCT PRICE_DA\nExamples:\n/price rtx 3070 88000\n/price rtx 3060 12gb 62000\n/price latitude 5440 70000")
        return
    product = match.group(1)
    value = float(re.sub(r"[^\d]", "", match.group(2)) or 0)
    key, description, kind = pricebook.key_from_text(product)
    if not key:
        _reply(settings, "I could not tell which product that is. Name a graphics card (rtx 3070) or a laptop model (latitude 5440). Laptop configurations are set in the app's price book.")
        return
    if not 10_000 <= value <= 2_000_000:
        _reply(settings, "That price looks wrong: give it in Algerian dinars, e.g. 88000.")
        return
    dz_market.set_manual_key(db, key, description, kind, value)
    priced = 0
    for search in db.query(Search).all():  # every ad of the product follows the new price at once
        priced += enrich.fill_from_book(db, settings, enrich._search_rows(db, search), search)
    _reply(settings, f"Saved: {description} = {value:,.0f} DA (yours, the AI will not change it). Profits recomputed.".replace(",", " "))


def _handle_message(db: Session, settings: Settings, message: dict[str, Any]) -> None:
    if not _chat_ok(settings, message.get("chat") or {}):
        return
    text = (message.get("text") or "").strip()
    if text.startswith(("/start", "/help")):
        _reply(settings, HELP)
    elif text.startswith("/deals"):
        browser.send_menu(db, settings)
    elif text.startswith("/best"):
        browser.open_search(db, settings, 0, "g")
    elif text.startswith("/price"):
        _set_price(db, settings, text)
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


def ready(settings: Settings) -> bool:
    return bool(settings.telegram_enabled and (settings.telegram_bot_token or "").strip() and (settings.telegram_chat_id or "").strip())


def process_updates(db: Session, settings: Settings, wait: int = 0) -> int:
    """Fetch and handle pending updates once (``wait`` seconds of long polling). Returns how many were handled."""
    if not ready(settings):
        return 0
    result = telegram.get_updates(settings.telegram_bot_token, int(settings.telegram_update_offset or 0), wait)
    if not result["ok"]:
        return 0
    handled = 0
    for update in result["result"] or []:
        # move the offset first: an update that crashes the handler is never fetched again
        settings.telegram_update_offset = update["update_id"] + 1
        db.commit()
        try:
            if update.get("callback_query"):
                _handle_callback(db, settings, update["callback_query"])
            elif update.get("message"):
                _handle_message(db, settings, update["message"])
            handled += 1
        except Exception as exc:  # one bad update must not block the queue
            db.rollback()
            print(f"[telegram] update {update['update_id']} failed: {type(exc).__name__}: {exc}")
    return handled
