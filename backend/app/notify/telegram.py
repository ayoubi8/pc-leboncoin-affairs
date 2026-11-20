"""Minimal Telegram Bot API client (httpx only). Never raises: returns {"ok": bool, ...}."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ..config import APP_URL
from ..models import Settings

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 20.0
PRIVATE_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


def _call(token: str, method: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "No Telegram bot token saved. Paste it in Settings and save first."}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(API.format(token=token, method=method), json=payload or {})
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"Telegram request failed: {type(exc).__name__}"}
    if not data.get("ok"):
        return {"ok": False, "error": f"Telegram: {data.get('description', 'unknown error')}"}
    return {"ok": True, "result": data.get("result")}


def build_markup(buttons: Optional[list[tuple[str, str]]]) -> Optional[dict[str, Any]]:
    """Buttons are (label, url) or (label, "cb:<data>") for a callback button.

    URL buttons go on the first row, callback buttons on the second. Telegram rejects
    localhost/private URLs, so those are dropped.
    """
    urls: list[dict[str, Any]] = []
    callbacks: list[dict[str, Any]] = []
    for label, target in buttons or []:
        if target.startswith("cb:"):
            callbacks.append({"text": label, "callback_data": target[3:][:64]})
        elif target.startswith("http") and not any(host in target for host in PRIVATE_HOSTS):
            urls.append({"text": label, "url": target})
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


def get_updates(token: str, offset: int = 0) -> dict[str, Any]:
    return _call(token, "getUpdates", {"offset": offset, "timeout": 0, "limit": 50, "allowed_updates": ["message", "callback_query"]})


def answer_callback(token: str, callback_id: str, text: str = "") -> dict[str, Any]:
    return _call(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})


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
