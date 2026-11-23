"""Telegram deal desk: only fresh, verified, profitable ads reach the phone.

Pipeline per run (cheap checks first, paid calls last):
 1. free gate: active, not rejected by the screen, young enough, fresh, has an Algerian price, shippable
 2. free maths gate: conservative profit (verdict.compute_numbers) must clear the threshold
 3. Haiku verdict for the survivors only
 4. rank by profit x freshness, verify the top ones are still online, send, stop at the per-run cap
"""

from __future__ import annotations

import html
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import APP_URL
from ..intelligence import freshness, match, negotiation, verdict
from ..models import Listing, Search, SearchListing, Settings
from ..scraping import leboncoin
from . import telegram

ORDER = ["skip", "fair", "good", "great"]
EMOJI = {"great": "🔥", "good": "✅", "fair": "🟡", "skip": "⛔"}
PRICE_DROP_REALERT = 0.95  # re-alert when the price falls below 95 % of the last alerted price


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def _eur(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:,.0f} €".replace(",", " ")


def _signed(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:+,.0f} €".replace(",", " ")


def _dzd(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:,.0f} DA".replace(",", " ")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def in_quiet_hours(settings: Settings, now: Optional[datetime] = None) -> bool:
    start, end = settings.quiet_start_hour, settings.quiet_end_hour
    if start is None or end is None or start == end:
        return False
    hour = ((now or _now()) + timedelta(hours=1)).hour  # Algeria is UTC+1 all year
    return start <= hour < end if start < end else (hour >= start or hour < end)


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


def _ship_line(listing: Listing) -> str:
    return {"yes": "📦 ships (Leboncoin delivery)", "no": "🚫 pickup only"}.get(listing.ship_ok or "", "📦 shipping not stated")


def format_message(
    listing: Listing,
    result: dict[str, Any],
    verified: Optional[str] = None,
    previous_price: Optional[float] = None,
) -> str:
    n = result["numbers"]
    label = result["verdict"]
    info = freshness.compute(listing)
    online = {"active": "✅ still online (checked)", "unknown": "⚠️ availability not verified"}.get(verified or "", "")
    title = "PRICE DROP" if previous_price else f"{label.upper()} DEAL"
    lines = [
        f"{'📉' if previous_price else EMOJI.get(label, '')} <b>{_esc(title)}</b> · {_esc(listing.subject)[:140]}",
        _spec_line(listing),
        f"🕒 {_esc(freshness.age_label(info['age_hours']))} · freshness {info['score']:.0f}/100" + (f" · {online}" if online else ""),
        _ship_line(listing),
        "",
        f"💶 <b>Leboncoin:</b> {_eur(n['ask_price_eur'])}"
        + (f" (was {_eur(previous_price)})" if previous_price else "")
        + f" → expected buy ~{_eur(n['buy_price_eur'])}",
        f"🚚 <b>Landed:</b> {_eur(n['total_cost_eur'])} ({_dzd(n['total_cost_dzd'])}) = shipping {_eur(n['shipping_eur'])} + customs {_eur(n['customs_eur'])}",
        f"🇩🇿 <b>Algeria:</b> {_dzd(n['dz_median_dzd'])} ≈ {_eur(n['dz_median_eur'])} asking"
        f" → {_eur(n['dz_net_eur'])} after {n['resale_haircut_pct']:.0f}% haircut ({_esc(n['dz_confidence'] or '?')} confidence)",
        f"📈 <b>Profit:</b> {_signed(n['profit_eur'])} ({n['margin_pct']}%) expected · {_signed(n['profit_ask_eur'])} at asking price",
        f"🎯 <b>Max to pay:</b> {_eur(result.get('max_buy_price_eur'))}",
    ]
    flags = [f for f in (listing.risk_flags or []) if "positive" not in f][:4]
    if flags:
        lines.append("⚠️ " + _esc(" · ".join(flags)))
    if result.get("headline"):
        lines += ["", f"💬 <b>{_esc(result['headline'])}</b>"]
    if result.get("opinion") and result.get("source") == "ai":
        lines.append(f"🧠 {_esc(str(result['opinion'])[:230])}")
    return "\n".join(lines)[:1020]


def negotiation_text(db: Session, settings: Settings, listing: Listing, numbers: dict[str, Any]) -> str:
    """French opening message, copy-paste ready; the offer sits below the price we expect to settle at."""
    ask = float(listing.price_eur or 0)
    target = numbers["buy_price_eur"]
    offer = max(round(target * 0.97 / 5) * 5, round(ask * 0.8 / 5) * 5)
    offer = min(offer, ask)
    try:
        built = negotiation.build(db, settings, listing, tone="friendly", offer_override=offer, use_ai=False)
        return built["message_fr"]
    except Exception:
        return f"Bonjour, votre annonce « {listing.subject[:80]} » est-elle toujours disponible ? Je peux vous proposer {offer:.0f} €, paiement rapide. Merci."


def _check_online(listing: Listing) -> str:
    """'active' | 'gone' | 'unknown' from the live ad page (one request, never raises)."""
    try:
        return leboncoin.check_ad_status(leboncoin.make_session(), listing.url or "")
    except Exception:
        return "unknown"


def _gate(settings: Settings, listing: Listing, realert: bool, search: Optional[Search] = None) -> bool:
    """Free checks. True when the ad may be considered for an alert."""
    if search is not None and match.hard_fail(search, listing):
        return False
    if listing.screen_skip or listing.gone_at is not None or listing.is_active is False:
        return False
    if not listing.price_eur or not listing.dz_price_median_dzd:
        return False
    if any("suspiciously" in f for f in (listing.risk_flags or [])):
        return False
    if listing.ship_ok == "no" and not settings.alert_pickup_only:
        return False
    info = freshness.compute(listing)
    max_age = float(settings.max_ad_age_hours or freshness.FRESH_HOURS)
    if info["age_hours"] is not None and info["age_hours"] > max_age:
        return False
    if freshness.sold_flags(listing):
        return False
    if realert:
        return bool(listing.price_alerted_eur) and listing.price_eur <= listing.price_alerted_eur * PRICE_DROP_REALERT
    return listing.notified_at is None


def notify_run(
    db: Session,
    settings: Settings,
    search: Search,
    new_listings: list[Listing],
    changed_listings: Optional[list[Listing]] = None,
) -> dict[str, int]:
    """Send the best fresh deals of a run. A listing is alerted once, plus once more if its price drops."""
    stats = {"candidates": 0, "verdicts": 0, "sent": 0, "gone": 0, "quiet": 0}
    min_label = settings.notify_min_verdict if settings.notify_min_verdict in ORDER else "good"
    limit = max(1, int(settings.notify_max_per_run or 5))

    pool = [(listing, False) for listing in new_listings] + [
        (listing, True) for listing in (changed_listings or []) if listing.notified_at is not None
    ]
    # An alert needs an Algerian price and an AI verdict, so the freshest new ads (max 5) get both first.
    # Ads of a product already in the price book only cost the verdict call.
    from ..intelligence import enrich

    try:
        stats["ai_checked"] = enrich.run_for(db, settings, search, [listing for listing, _ in pool])
    except Exception as exc:  # alerts still go out for ads that were already priced
        print(f"[notify] AI step failed: {type(exc).__name__}: {exc}")
    candidates = [(l, r) for l, r in pool if _gate(settings, l, r, search)]
    stats["candidates"] = len(candidates)

    # free maths gate -> paid verdict only for ads that already look profitable on conservative numbers
    scored: list[tuple[Listing, bool, dict[str, Any]]] = []
    for listing, realert in candidates:
        numbers = verdict.compute_numbers(settings, listing)
        if numbers is None or numbers["profit_ask_eur"] <= 0:
            continue
        if ORDER.index(verdict.label_for(numbers["margin_pct"], numbers["dz_confidence"])) < ORDER.index(min_label):
            continue
        try:
            # Scans never call a model: an ad that already has an AI verdict keeps it, others get the rule-based one.
            result = listing.ai_verdict if (listing.ai_verdict and listing.ai_verdict.get("numbers")) else verdict.apply(db, settings, listing, use_ai=False)
        except Exception:
            continue
        stats["verdicts"] += 1
        if ORDER.index(result["verdict"]) >= ORDER.index(min_label):
            scored.append((listing, realert, result))

    def rank(item: tuple[Listing, bool, dict[str, Any]]) -> float:
        listing, _, result = item
        return result["numbers"]["profit_eur"] * (0.5 + (listing.freshness_score or 50) / 200)

    scored.sort(key=rank, reverse=True)

    if in_quiet_hours(settings):
        stats["quiet"] = len(scored)  # keep them un-notified; they go out after quiet hours if still fresh
        return stats

    sent = 0
    checks = 0
    for listing, realert, result in scored:
        if sent >= limit or checks >= limit * 2:
            break
        checks += 1
        state = _check_online(listing)
        listing.last_checked_at = _now()
        if state == "gone":
            listing.is_active = False
            listing.gone_at = _now()
            listing.freshness_score = 0.0
            stats["gone"] += 1
            continue

        images = listing.images or []
        photo = images[0] if images and isinstance(images[0], str) else None
        previous = listing.price_alerted_eur if realert else None
        first = telegram.send_message(
            settings,
            format_message(listing, result, state, previous),
            photo_url=photo,
            buttons=[
                ("Open ad", listing.url or ""),
                ("Open in app", f"{APP_URL}/listings/{listing.id}"),
                ("📨 Contacted", f"cb:p:c:{listing.id}"),
                ("✅ Bought", f"cb:p:b:{listing.id}"),
                ("⏭ Skip", f"cb:p:s:{listing.id}"),
            ],
        )
        if not first["ok"]:
            print(f"[notify] telegram send failed: {first['error']}")
            break  # bad token/chat: stop spamming errors, retry next run
        telegram.send_message(
            settings,
            "✍️ <b>Message to send</b> (tap to copy):\n<code>"
            + _esc(negotiation_text(db, settings, listing, result["numbers"]))
            + "</code>",
            reply_to=telegram.message_id(first),
        )
        listing.notified_at = _now()
        listing.price_alerted_eur = listing.price_eur
        sent += 1
    stats["sent"] = sent
    db.commit()

    extra = len(scored) - sent - stats["gone"]
    if extra > 0 and sent:
        telegram.send_message(
            settings,
            f"➕ {extra} more good deal(s) from “{_esc(search.name)}”.",
            buttons=[("See all", f"{APP_URL}/deals")],
        )
    return stats


# --- /deals command and scan summaries: free, they only read what is already stored ---

CLOSED_STATUSES = ("bought", "shipped", "sold", "skipped")
AUTO_SUMMARY_GAP_S = 60 * 60  # automatic scans can run every 10 min: at most one summary per search per hour
_last_summary: dict[int, float] = {}


def top_fresh(
    db: Session, settings: Settings, search: Optional[Search] = None, limit: int = 5, order: str = "newest"
) -> list[Listing]:
    """Actionable fresh ads, losing ones included. ``order``: "newest" first, or "profit" (priced ads first)."""
    query = (
        select(Listing, Search)
        .join(SearchListing, SearchListing.listing_id == Listing.id)
        .join(Search, Search.id == SearchListing.search_id)
    )
    if search is not None:
        query = query.where(Search.id == search.id)
    now = _now()
    max_age = float(settings.max_ad_age_hours or freshness.FRESH_HOURS)
    chosen: dict[int, Listing] = {}
    for listing, owner in db.execute(query).all():
        if listing.id in chosen or listing.gone_at is not None or listing.is_active is False or listing.screen_skip:
            continue
        if (listing.pipeline_status or "") in CLOSED_STATUSES or not listing.price_eur:
            continue
        if listing.ship_ok == "no" and not settings.alert_pickup_only:
            continue
        age = freshness.age_hours(listing, now)
        if (age is not None and age > max_age) or match.hard_fail(owner, listing):
            continue
        chosen[listing.id] = listing

    def rank(listing: Listing) -> tuple[int, float]:
        age = freshness.age_hours(listing, now)
        if order == "newest":
            return (age is None, age or 0.0)
        numbers = verdict.compute_numbers(settings, listing)
        return (1, age or 0.0) if numbers is None else (0, -numbers["profit_ask_eur"])

    return sorted(chosen.values(), key=rank)[:limit]


def deal_card(settings: Settings, listing: Listing, position: int) -> str:
    numbers = verdict.compute_numbers(settings, listing)
    label = listing.ai_verdict_label if listing.ai_verdict_label in ORDER else ""
    if not label and numbers:
        label = verdict.label_for(numbers["margin_pct"], numbers["dz_confidence"])
    age = freshness.age_label(freshness.age_hours(listing))
    lines = [
        f"{EMOJI.get(label, '⏳')} <b>{position}. {_esc(label.upper() or 'NOT PRICED YET')}</b> · {_esc(listing.subject)[:110]}",
        _spec_line(listing),
        f"🕒 {_esc(age)} · {_ship_line(listing)}",
        f"💶 <b>Price:</b> {_eur(listing.price_eur)}",
    ]
    if numbers:
        word = "Profit" if numbers["profit_ask_eur"] >= 0 else "Loss"
        lines += [
            f"🚚 <b>Landed:</b> {_eur(numbers['total_cost_ask_eur'])}",
            f"🇩🇿 <b>Algeria:</b> {_dzd(numbers['dz_median_dzd'])} ({_esc(numbers['dz_confidence'] or '?')} confidence)",
            f"📈 <b>{word} at asking price:</b> {_signed(numbers['profit_ask_eur'])} ({numbers['margin_ask_pct']}%)",
            f"🎯 <b>Max to pay:</b> {_eur(numbers['max_buy_for_good_eur'])}",
        ]
    else:
        lines.append("No Algerian price yet: open Fresh ads in the app to run the AI on it.")
    stored = listing.ai_verdict or {}
    if stored.get("source") == "ai" and stored.get("headline"):
        lines.append(f"💬 {_esc(stored['headline'])}")
    return "\n".join(lines)


def send_top_deals(db: Session, settings: Settings, limit: int = 5) -> int:
    """Answer /deals: one message per ad, each with its link. Returns how many ads were sent."""
    listings = top_fresh(db, settings, limit=limit)
    if not listings:
        telegram.send_message(settings, "No fresh ad to show: everything is older than the max age, gone, pickup only, or off-search. Run a scan first.")
        return 0
    max_age = float(settings.max_ad_age_hours or freshness.FRESH_HOURS)
    telegram.send_message(settings, f"📋 <b>{len(listings)} newest fresh ads</b> (under {max_age / 24:.0f} days). Losing ads are shown too, marked as such.")
    for position, listing in enumerate(listings, start=1):
        telegram.send_message(
            settings,
            deal_card(settings, listing, position),
            buttons=[
                ("Open ad", listing.url or ""),
                ("Open in app", f"{APP_URL}/listings/{listing.id}"),
                ("📨 Contacted", f"cb:p:c:{listing.id}"),
                ("⏭ Skip", f"cb:p:s:{listing.id}"),
            ],
        )
    return len(listings)


def send_scan_summary(
    db: Session,
    settings: Settings,
    search: Search,
    trigger: str,
    checked: int,
    new: int,
    stats: Optional[dict[str, Any]] = None,
) -> bool:
    """A short note after a scan so silence never looks like a broken bot.

    Manual scans always report. Automatic ones only when they found new ads, at most hourly, never in quiet hours.
    """
    if trigger != "manual":
        if not new or in_quiet_hours(settings) or time.time() - _last_summary.get(search.id, 0) < AUTO_SUMMARY_GAP_S:
            return False
    sent = int((stats or {}).get("sent") or 0)
    lines = [f"📊 <b>{_esc(search.name)}</b>: {checked} ads checked, {new} new, {sent} good deal{'' if sent == 1 else 's'} sent."]
    best = top_fresh(db, settings, search, limit=1, order="profit")
    numbers = verdict.compute_numbers(settings, best[0]) if best else None
    if numbers:
        lines.append(f"Best fresh ad: {_esc(best[0].subject)[:60]} · {_eur(best[0].price_eur)} · {_signed(numbers['profit_ask_eur'])} at asking price")
    elif best:
        lines.append("Fresh ads are waiting for an Algerian price.")
    else:
        lines.append("No fresh ad you could buy right now.")
    lines.append("Send /deals to see the 5 newest.")
    result = telegram.send_message(settings, "\n".join(lines))
    if result.get("ok"):
        _last_summary[search.id] = time.time()
    return bool(result.get("ok"))
