"""Telegram deal browser.

/deals lists your searches with their good and unseen deals. Tapping one opens a single card that changes in
place with Next / Prev, so you go through a search's best deals one by one without filling the chat.

Button data carries everything needed (search, current ad, mode), so nothing is lost when the bot restarts:
  m                    the search menu
  o:<search>:<mode>    open a search at its first unseen deal (search 0 = all searches)
  n / b:<search>:<ad>:<mode>  next / previous
  k / c / y:<search>:<ad>:<mode>  skip / contacted / bought
Modes: g = deals with a profit at the asking price, a = every fresh ad.
"""

from __future__ import annotations

import html
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..intelligence import freshness, verdict
from ..models import Listing, Search, Settings
from . import deals, pipeline, telegram

ROW = ("", telegram.ROW)
ACTIONS = {"k": "skipped", "c": "contacted", "y": "bought"}
STATUS_LINE = {"contacted": "📨 You contacted the seller", "bought": "✅ Marked as bought", "skipped": "⏭ Skipped"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def search_label(search: Optional[Search]) -> str:
    """A readable name: the searched card or CPU says more than names like "pc portable"."""
    if search is None:
        return "All searches"
    what = " ".join(x for x in ((search.gpu or "").strip(), (search.cpu or "").strip()) if x)
    return (what.upper() if search.gpu else what) or search.name or f"Search {search.id}"


def queue(
    db: Session, settings: Settings, search_id: int, mode: str = "g"
) -> tuple[list[tuple[Listing, Search, Optional[dict[str, Any]]]], dict[str, int]]:
    """The ads of a search in browsing order, and counts of what was left out.

    Best profit at the asking price first, then the newest. Mode "g" keeps only ads with a profit.
    """
    search = db.get(Search, search_id) if search_id else None
    pairs, pickup = deals.fresh_pairs(db, settings, search)
    now = deals._now()
    rows = []
    for listing, owner in pairs.values():
        rows.append((listing, owner, verdict.compute_numbers(settings, listing)))
    good = [r for r in rows if r[2] is not None and r[2]["profit_ask_eur"] > 0]
    losing = sum(1 for r in rows if r[2] is not None and r[2]["profit_ask_eur"] <= 0)
    unpriced = sum(1 for r in rows if r[2] is None)

    def rank(row: tuple[Listing, Search, Optional[dict[str, Any]]]) -> tuple[int, float, float]:
        listing, _, numbers = row
        age = freshness.age_hours(listing, now)
        if numbers is None:
            return (1, 0.0, age if age is not None else 1e9)
        return (0, -numbers["profit_ask_eur"], age if age is not None else 1e9)

    chosen = good if mode == "g" else rows
    chosen.sort(key=rank)
    counts = {"good": len(good), "losing": losing, "unpriced": unpriced, "pickup": pickup,
              "new_good": sum(1 for r in good if r[0].tg_seen_at is None),
              "new": sum(1 for r in rows if r[0].tg_seen_at is None)}
    return chosen, counts


def menu(db: Session, settings: Settings) -> tuple[str, list[tuple[str, str]]]:
    searches = db.execute(select(Search).order_by(Search.id)).scalars().all()
    lines = ["📋 <b>Your searches</b>", "Tap one to go through its deals, best profit first.", ""]
    buttons: list[tuple[str, str]] = []
    total_good = 0
    for search in searches:
        _, counts = queue(db, settings, search.id, "g")
        total_good += counts["good"]
        fire = "🔥 " if counts["new_good"] else ""
        lines.append(
            f"{fire}<b>{_esc(search_label(search))}</b>: {counts['good']} good ({counts['new_good']} new) · "
            f"{counts['new']} unseen ads"
            + (f" · {counts['unpriced']} not priced yet" if counts["unpriced"] else "")
        )
        buttons += [(f"{fire}{search_label(search)} · {counts['good']} good · {counts['new']} new", f"cb:o:{search.id}:g"), ROW]
    if not searches:
        lines.append("No search yet. Create one in the app.")
    buttons.append((f"⭐ Best of all searches ({total_good})", "cb:o:0:g"))
    lines += ["", "Good = profit when you pay the asking price. Pickup-only ads are left out."]
    return "\n".join(lines), buttons


def card(
    settings: Settings, listing: Listing, owner: Optional[Search], numbers: Optional[dict[str, Any]], position: str
) -> str:
    label = listing.ai_verdict_label if listing.ai_verdict_label in deals.ORDER else ""
    if not label and numbers:
        label = verdict.label_for(numbers["margin_pct"], numbers["dz_confidence"])
    new = " · 🆕" if listing.tg_seen_at is None else ""
    lines = [
        f"{deals.EMOJI.get(label, '⏳')} <b>{_esc(label.upper() or 'NOT PRICED')}</b> · {position} · {_esc(search_label(owner))}{new}",
        f"<b>{_esc(listing.subject)[:100]}</b>",
    ]
    spec = deals._spec_line(listing)
    if spec:
        lines.append(spec[:160])
    if numbers:
        lines += [
            f"💶 {deals._eur(listing.price_eur)} → 🚚 landed {deals._eur(numbers['total_cost_ask_eur'])}"
            f" · 🇩🇿 {deals._dzd(numbers['dz_median_dzd'])} ({_esc(numbers['dz_confidence'] or '?')})",
            f"📈 <b>{deals._signed(numbers['profit_ask_eur'])}</b> ({numbers['margin_ask_pct']}%) at asking price"
            f" · 🎯 pay max {deals._eur(numbers['max_buy_for_good_eur'])}",
        ]
    else:
        lines.append(f"💶 {deals._eur(listing.price_eur)} · no Algerian price for this product yet")
    lines.append(f"🕒 {_esc(freshness.age_label(freshness.age_hours(listing)))} · {deals._ship_line(listing)}")
    flags = [f for f in (listing.risk_flags or []) if "positive" not in f][:2]
    if flags:
        lines.append("⚠️ " + _esc(" · ".join(flags))[:200])
    if listing.pipeline_status in STATUS_LINE:
        lines.append(STATUS_LINE[listing.pipeline_status])
    return "\n".join(lines)[:1020]


def _card_buttons(listing: Listing, search_id: int, mode: str) -> list[tuple[str, str]]:
    ref = f"{search_id}:{listing.id}:{mode}"
    status = listing.pipeline_status or ""
    toggle = ("Show losing ads too", f"cb:o:{search_id}:a") if mode == "g" else ("Good deals only", f"cb:o:{search_id}:g")
    return [
        ("Open ad", listing.url or ""), ROW,
        ("◀ Prev", f"cb:b:{ref}"), ("Next ▶", f"cb:n:{ref}"), ROW,
        ("⏭ Skip", f"cb:k:{ref}"),
        ("📨 Contacted ✓" if status == "contacted" else "📨 Contacted", f"cb:c:{ref}"),
        ("✅ Bought ✓" if status == "bought" else "✅ Bought", f"cb:y:{ref}"), ROW,
        ("↩ Searches", "cb:m"), toggle,
    ]


def _empty(db: Session, settings: Settings, search_id: int, mode: str) -> tuple[str, list[tuple[str, str]]]:
    _, counts = queue(db, settings, search_id, "a")
    name = search_label(db.get(Search, search_id) if search_id else None)
    hidden = []
    if counts["losing"]:
        hidden.append(f"{counts['losing']} losing")
    if counts["unpriced"]:
        hidden.append(f"{counts['unpriced']} not priced yet")
    if counts["pickup"]:
        hidden.append(f"{counts['pickup']} pickup-only")
    text = (f"✅ <b>{_esc(name)}</b>: no deal with a profit right now." if mode == "g" else f"<b>{_esc(name)}</b>: no fresh ad right now.")
    if hidden:
        text += "\nLeft out: " + ", ".join(hidden) + " ad(s)."
    buttons = [("↩ Searches", "cb:m")]
    if mode == "g" and (counts["losing"] or counts["unpriced"]):
        buttons.append(("Show losing ads too", f"cb:o:{search_id}:a"))
    return text, buttons


def _put(settings: Settings, message: Optional[dict[str, Any]], text: str, photo: Optional[str], buttons: list[tuple[str, str]]) -> None:
    """Show ``text`` in place of ``message`` when Telegram allows it, otherwise as a new message (the old one goes)."""
    if message and message.get("message_id"):
        result = telegram.edit_card(settings, int(message["message_id"]), text, photo, buttons, is_photo=bool(message.get("photo")))
        if result["ok"] or "not modified" in result.get("error", ""):
            return
        telegram.delete_message(settings, int(message["message_id"]))
    telegram.send_message(settings, text, photo_url=photo, buttons=buttons)


def _photo(listing: Listing) -> Optional[str]:
    images = listing.images or []
    return images[0] if images and isinstance(images[0], str) else None


def show(db: Session, settings: Settings, message: Optional[dict[str, Any]], search_id: int, mode: str, index: int) -> None:
    rows, _ = queue(db, settings, search_id, mode)
    if not rows:
        text, buttons = _empty(db, settings, search_id, mode)
        _put(settings, message, text, None, buttons)
        return
    index = max(0, min(index, len(rows) - 1))
    listing, owner, numbers = rows[index]
    _show_one(db, settings, message, listing, owner, numbers, f"{index + 1}/{len(rows)}", search_id, mode)


def _show_one(db, settings, message, listing, owner, numbers, position, search_id, mode) -> None:
    _put(settings, message, card(settings, listing, owner, numbers, position), _photo(listing), _card_buttons(listing, search_id, mode))
    if listing.tg_seen_at is None:
        listing.tg_seen_at = deals._now()
        db.commit()


def send_menu(db: Session, settings: Settings, message: Optional[dict[str, Any]] = None) -> None:
    text, buttons = menu(db, settings)
    _put(settings, message, text, None, buttons)


def open_search(db: Session, settings: Settings, search_id: int, mode: str = "g", message: Optional[dict[str, Any]] = None) -> None:
    """Start at the first deal you have not seen yet (or the best one when you have seen them all)."""
    rows, _ = queue(db, settings, search_id, mode)
    first_new = next((i for i, row in enumerate(rows) if row[0].tg_seen_at is None), 0)
    show(db, settings, message, search_id, mode, first_new)


def _position(rows: list[tuple[Listing, Search, Any]], listing_id: int) -> Optional[int]:
    return next((i for i, row in enumerate(rows) if row[0].id == listing_id), None)


def handle(db: Session, settings: Settings, data: str, message: Optional[dict[str, Any]]) -> str:
    """Handle a browser button. Returns a short note for Telegram's pop-up ("" for none)."""
    parts = data.split(":")
    kind = parts[0]
    if kind == "m":
        send_menu(db, settings, message)
        return ""
    if kind == "o" and len(parts) == 3:
        open_search(db, settings, int(parts[1]), parts[2], message)
        return ""
    if len(parts) != 4:
        return "Unknown button"
    search_id, listing_id, mode = int(parts[1]), int(parts[2]), parts[3]
    rows, _ = queue(db, settings, search_id, mode)
    here = _position(rows, listing_id)

    if kind in ("n", "b"):
        if here is None:
            show(db, settings, message, search_id, mode, 0)
            return ""
        target = here + (1 if kind == "n" else -1)
        if target < 0 or target >= len(rows):
            return "That was the last one" if kind == "n" else "This is the first one"
        show(db, settings, message, search_id, mode, target)
        return ""

    if kind in ACTIONS:
        listing = db.get(Listing, listing_id)
        if listing is None:
            return "Ad not found"
        status = ACTIONS[kind]
        if kind != "k" and listing.pipeline_status == status:
            status = ""  # tapping a ticked button again removes the mark
        pipeline.set_status(db, settings, listing, status)
        if kind == "k":
            show(db, settings, message, search_id, mode, here or 0)  # the next ad takes the skipped one's place
            return "Skipped"
        numbers = verdict.compute_numbers(settings, listing)
        owner = db.get(Search, search_id) if search_id else (rows[here][1] if here is not None else None)
        position = f"{here + 1}/{len(rows)}" if here is not None else "—"
        _show_one(db, settings, message, listing, owner, numbers, position, search_id, mode)
        return {"contacted": "Marked as contacted", "bought": "Marked as bought: send /paid to record the price", "": "Mark removed"}[status]
    return "Unknown button"
