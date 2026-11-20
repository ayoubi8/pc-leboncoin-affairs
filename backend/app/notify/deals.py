"""Telegram alerts for the best brand-new deals found by a search run."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..config import APP_URL
from ..intelligence import verdict
from ..models import Listing, Search, Settings
from . import telegram

ORDER = ["skip", "fair", "good", "great"]
EMOJI = {"great": "🔥", "good": "✅", "fair": "🟡", "skip": "⛔"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def _eur(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:,.0f} €".replace(",", " ")


def _dzd(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:,.0f} DA".replace(",", " ")


def _spec_line(listing: Listing) -> str:
    specs = listing.specs or {}
    parts = [
        specs.get("cpu"),
        f"{specs['ram_gb']} GB RAM" if specs.get("ram_gb") else None,
        f"{specs['storage_gb']} GB" if specs.get("storage_gb") else None,
        specs.get("gpu"),
        f"{specs['screen_inches']}\"" if specs.get("screen_inches") else None,
        specs.get("brand") or listing.brand,
        specs.get("condition") or listing.condition,
        listing.city,
    ]
    return " · ".join(_esc(p) for p in parts if p)


def format_message(listing: Listing, result: dict[str, Any]) -> str:
    n = result["numbers"]
    label = result["verdict"]
    published = (listing.first_publication_date or "")[:10]
    lines = [
        f"{EMOJI.get(label, '')} <b>{_esc(label.upper())} DEAL</b> · {_esc(listing.subject)[:140]}",
        _spec_line(listing) + (f" · published {_esc(published)}" if published else ""),
        "",
        f"💶 <b>Leboncoin:</b> {_eur(n['ask_price_eur'])}"
        + (f" → negotiate to ~{_eur(n['buy_price_eur'])}" if n["negotiation_saving_eur"] > 0 else ""),
        f"🚚 <b>Landed in Algeria:</b> {_eur(n['total_cost_eur'])} ({_dzd(n['total_cost_dzd'])})",
        f"🇩🇿 <b>Algeria market:</b> {_dzd(n['dz_median_dzd'])} ≈ {_eur(n['dz_median_eur'])}"
        f" ({_esc(n['dz_confidence'] or '?')} confidence)",
        f"📈 <b>Estimated profit:</b> {_eur(n['profit_eur'])} ({n['margin_pct']}%)"
        f" · max to pay {_eur(result.get('max_buy_price_eur'))}",
    ]
    if result.get("headline"):
        lines += ["", f"💬 {_esc(result['headline'])}"]
    return "\n".join(lines)


def notify_run(db: Session, settings: Settings, search: Search, new_listings: list[Listing]) -> dict[str, int]:
    """Send the best new deals of a run. Each listing is alerted at most once (notified_at)."""
    stats = {"candidates": 0, "verdicts": 0, "sent": 0}
    min_label = settings.notify_min_verdict if settings.notify_min_verdict in ORDER else "good"
    limit = max(1, int(settings.notify_max_per_run or 5))

    # 1) cheap prefilter - no paid calls: needs an Algerian price that beats the landed cost
    candidates = [
        l for l in new_listings
        if l.notified_at is None and l.price_eur and l.dz_price_median_dzd and (l.dz_saving_pct or 0) > 0
    ]
    stats["candidates"] = len(candidates)

    # 2) honest verdict (Haiku) only for those
    good: list[tuple[Listing, dict[str, Any]]] = []
    for listing in candidates:
        try:
            result = verdict.apply(db, settings, listing)
        except Exception:
            continue
        stats["verdicts"] += 1
        if ORDER.index(result["verdict"]) >= ORDER.index(min_label):
            good.append((listing, result))

    good.sort(key=lambda item: item[1]["numbers"]["profit_eur"], reverse=True)

    # 3) send the top N, one message each
    for listing, result in good[:limit]:
        images = listing.images or []
        photo = images[0] if images and isinstance(images[0], str) else None
        sent = telegram.send_message(
            settings,
            format_message(listing, result),
            photo_url=photo,
            buttons=[("Open ad", listing.url or ""), ("Open in app", f"{APP_URL}/listings/{listing.id}")],
        )
        if sent["ok"]:
            listing.notified_at = datetime.now(timezone.utc).replace(tzinfo=None)
            stats["sent"] += 1
        else:
            print(f"[notify] telegram send failed: {sent['error']}")
            break  # bad token/chat: stop spamming errors, retry next run
    db.commit()

    extra = len(good) - limit
    if extra > 0 and stats["sent"]:
        telegram.send_message(
            settings,
            f"➕ {extra} more good deal(s) from “{_esc(search.name)}”.",
            buttons=[("See all", f"{APP_URL}/deals")],
        )
    return stats
