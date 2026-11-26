"""Minimal Telegram Bot API client (httpx only). Never raises: returns {"ok": bool, ...}."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ..config import APP_URL
from ..models import Settings

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 20.0
PRIVATE_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")
ROW = "|row|"  # button target that starts a new keyboard row


def _call(token: str, method: str, payload: Optional[dict[str, Any]] = None, timeout: float = TIMEOUT) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "No Telegram bot token saved. Paste it in Settings and save first."}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(API.format(token=token, method=method), json=payload or {})
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"Telegram request failed: {type(exc).__name__}"}
    if not data.get("ok"):
        return {"ok": False, "error": f"Telegram: {data.get('description', 'unknown error')}"}
    return {"ok": True, "result": data.get("result")}


def build_markup(buttons: Optional[list[tuple[str, str]]]) -> Optional[dict[str, Any]]:
    """Buttons are (label, url) or (label, "cb:<data>") for a callback button.

    URL buttons go on the first row, callback buttons on the second, unless a ("", ROW) marker sets the rows
    explicitly. Telegram rejects localhost/private URLs, so those are dropped.
    """
    def button(label: str, target: str) -> Optional[dict[str, Any]]:
        if target.startswith("cb:"):
            return {"text": label, "callback_data": target[3:][:64]}
        if target.startswith("http") and not any(host in target for host in PRIVATE_HOSTS):
            return {"text": label, "url": target}
        return None

    if any(target == ROW for _, target in buttons or []):
        rows: list[list[dict[str, Any]]] = [[]]
        for label, target in buttons or []:
            if target == ROW:
                rows.append([])
            elif (made := button(label, target)) is not None:
                rows[-1].append(made)
        rows = [row for row in rows if row]
        return {"inline_keyboard": rows} if rows else None

    urls: list[dict[str, Any]] = []
    callbacks: list[dict[str, Any]] = []
    for label, target in buttons or []:
        made = button(label, target)
        if made is not None:
            (callbacks if "callback_data" in made else urls).append(made)
    rows = [row for row in (urls, callbacks) if row]
    return {"inline_keyboard": rows} if rows else None


def send_message(
    settings: Settings,
    text: str,
    photo_url: Optional[str] = None,
    buttons: Optional[list[tuple[str, str]]] = None,
    reply_to: Optional[int] = None,
) -> dict[str, Any]:
    chat_id = (settings.telegram_chat_id or "").strip()
    if not chat_id:
        return {"ok": False, "error": "No chat id yet. Message your bot, then click Detect chat."}

    markup = build_markup(buttons)

    if photo_url and len(text) <= 1024:
        payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url, "caption": text, "parse_mode": "HTML"}
        if markup:
            payload["reply_markup"] = markup
        result = _call(settings.telegram_bot_token, "sendPhoto", payload)
        if result["ok"]:
            return result  # otherwise (bad image URL, etc.) fall back to plain text

    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if markup:
        payload["reply_markup"] = markup
    if reply_to:
        payload["reply_to_message_id"] = reply_to
        payload["allow_sending_without_reply"] = True
    return _call(settings.telegram_bot_token, "sendMessage", payload)


def message_id(result: dict[str, Any]) -> Optional[int]:
    value = (result.get("result") or {}).get("message_id") if isinstance(result.get("result"), dict) else None
    return int(value) if value is not None else None


def get_updates(token: str, offset: int = 0, wait: int = 0) -> dict[str, Any]:
    """``wait`` > 0 is long polling: Telegram holds the request until an update arrives, so taps are handled at once."""
    payload = {"offset": offset, "timeout": wait, "limit": 50, "allowed_updates": ["message", "callback_query"]}
    return _call(token, "getUpdates", payload, timeout=TIMEOUT + wait)


def answer_callback(token: str, callback_id: str, text: str = "") -> dict[str, Any]:
    return _call(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})


def edit_card(
    settings: Settings,
    message_id: int,
    text: str,
    photo_url: Optional[str],
    buttons: Optional[list[tuple[str, str]]],
    is_photo: bool,
) -> dict[str, Any]:
    """Change a message in place. A text message cannot become a photo (or the reverse), so the caller sends a new
    one when this fails."""
    chat_id = (settings.telegram_chat_id or "").strip()
    markup = build_markup(buttons) or {"inline_keyboard": []}
    if is_photo and photo_url and len(text) <= 1024:
        media = {"type": "photo", "media": photo_url, "caption": text, "parse_mode": "HTML"}
        return _call(settings.telegram_bot_token, "editMessageMedia",
                     {"chat_id": chat_id, "message_id": message_id, "media": media, "reply_markup": markup})
    if is_photo:
        return {"ok": False, "error": "photo message, card has no photo"}
    return _call(settings.telegram_bot_token, "editMessageText", {
        "chat_id": chat_id, "message_id": message_id, "text": text[:4000], "parse_mode": "HTML",
        "disable_web_page_preview": True, "reply_markup": markup,
    })


def edit_buttons(settings: Settings, message_id: int, buttons: Optional[list[tuple[str, str]]]) -> dict[str, Any]:
    markup = build_markup(buttons) or {"inline_keyboard": []}
    return _call(settings.telegram_bot_token, "editMessageReplyMarkup",
                 {"chat_id": (settings.telegram_chat_id or "").strip(), "message_id": message_id, "reply_markup": markup})


def delete_message(settings: Settings, message_id: int) -> dict[str, Any]:
    return _call(settings.telegram_bot_token, "deleteMessage",
                 {"chat_id": (settings.telegram_chat_id or "").strip(), "message_id": message_id})


COMMANDS = [
    ("deals", "Your searches with their unseen good deals"),
    ("best", "Best deals of all searches, one by one"),
    ("price", "Set a product's Algerian price: /price rtx 3070 88000"),
    ("status", "System health"),
    ("help", "All commands"),
]


def set_commands(token: str) -> dict[str, Any]:
    """Show the commands in Telegram's / menu."""
    return _call(token, "setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})


def detect_chat(token: str) -> dict[str, Any]:
    """Find the most recent chat that wrote to the bot (user pressed Start / sent a message)."""
    result = _call(token, "getUpdates", {"timeout": 0, "limit": 20})
    if not result["ok"]:
        return result
    for update in reversed(result["result"] or []):
        message = update.get("message") or update.get("channel_post") or update.get("my_chat_member") or {}
        chat = message.get("chat") or {}
        if chat.get("id") is not None:
            title = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
            return {"ok": True, "chat_id": chat["id"], "title": title}
    return {"ok": False, "error": "No message found. Open your bot in Telegram, press Start, send 'hi', then try again."}


def send_test(settings: Settings) -> dict[str, Any]:
    return send_message(
        settings,
        "✅ <b>Deal Finder</b> is connected. You will get new good deals here.",
        buttons=[("Open app", APP_URL)],
    )
