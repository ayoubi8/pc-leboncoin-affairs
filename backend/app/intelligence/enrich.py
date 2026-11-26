"""On-demand AI for the top ads of the Hot deals / Fresh ads views.

Automatic runs (page open, alerts) make ONE price request per product not yet in the price book; every
ad of that product then gets its profit and verdict by plain maths. The "Run AI" button does the full
three steps on the first ``TOP_N`` ads:

1. specs    - a free model (``Settings.spec_model``) fills the missing specs, explains why, writes a product description
2. price    - the Algerian price (``Settings.gemini_model``, with web search), cached per product in the price book
3. verdict  - Claude Haiku (``Settings.verdict_model``) writes the resale verdict from the computed numbers

Progress is kept in memory per search so the page can show it live.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..extraction import cpu_db, llm
from ..models import Listing, Search, SearchListing, Settings
from . import analyze, dz_market, freshness, match, pricebook, verdict

TOP_N = 5
COOLDOWN_S = 15 * 60  # automatic runs on page open: at most one batch per search every 15 minutes
STEPS = ("specs", "price", "verdict")

_jobs: dict[int, dict[str, Any]] = {}
_last_auto: dict[int, float] = {}
_failed: set[tuple[int, str]] = set()  # (listing id, step) that failed: not retried automatically
_lock = threading.Lock()


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def needs(listing: Listing, full: bool = True) -> list[str]:
    """Steps this ad still lacks. ``full=False``: only the Algerian price."""
    todo = []
    if full and not (listing.spec_notes or {}).get("model"):
        todo.append("specs")
    if not listing.dz_price_median_dzd:
        todo.append("price")
    if full and (listing.ai_verdict or {}).get("source") != "ai":
        todo.append("verdict")
    return [step for step in todo if (listing.id, step) not in _failed]


def _freshest_needing_ai(rows: list[Listing], search: Search, settings: Settings, limit: int, full: bool = True) -> list[Listing]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    max_age = float(settings.max_ad_age_hours or freshness.FRESH_HOURS)
    candidates = []
    for listing in rows:
        if listing.gone_at is not None or listing.is_active is False or listing.screen_skip:
            continue
        age = freshness.age_hours(listing, now)
        if age is not None and age > max_age:
            continue
        if match.hard_fail(search, listing):
            continue
        if not needs(listing, full):
            continue
        candidates.append((age if age is not None else 1e9, listing))
    candidates.sort(key=lambda pair: pair[0])
    picked: list[Listing] = []
    products: set[str] = set()
    for _, listing in candidates:
        if not full:  # one request per product
            key = dz_market.describe(listing)[0]
            if not key or key in products or not pricebook.is_specific(key):  # never spend on a vague ad
                continue
            products.add(key)
        picked.append(listing)
        if len(picked) >= limit:
            break
    return picked


def fill_from_book(db: Session, settings: Settings, listings: list[Listing], search: Optional[Search] = None) -> int:
    """Give ads the stored price of their product and compute profit and verdict. Free. Returns ads priced."""
    done = 0
    for listing in listings:
        if listing.screen_skip or not listing.price_eur:
            continue
        if search is not None and match.hard_fail(search, listing):
            continue
        # The ad follows its product's current price, so a re-priced (or hand-set) product reaches every ad of it.
        row = dz_market.lookup(db, settings, listing, allow_call=False) if dz_market.available(settings) else None
        if not listing.dz_price_median_dzd or (row is not None and row.median_dzd != listing.dz_price_median_dzd):
            analyze.apply_dz_comparison(db, settings, listing, allow_call=False)
        if verdict.apply_math(settings, listing):
            done += 1
    db.commit()
    return done


def _search_rows(db: Session, search: Search) -> list[Listing]:
    return list(
        db.execute(
            select(Listing).join(SearchListing, SearchListing.listing_id == Listing.id).where(SearchListing.search_id == search.id)
        ).scalars().all()
    )


def pick(db: Session, search: Search, settings: Settings, limit: int = TOP_N, full: bool = True) -> list[Listing]:
    """The freshest ads of the search that still need AI (``full=False``: one per unpriced product)."""
    rows = _search_rows(db, search)
    if not full:
        fill_from_book(db, settings, rows, search)  # products already known cost nothing
    return _freshest_needing_ai(rows, search, settings, limit, full)


PRICES_PER_RUN = 10  # new products priced per scan (the daily cap still applies)
SPECS_PER_RUN = 8  # ads read by the spec model per scan (free models allow ~20 requests a minute)


def _unknown_product(listing: Listing) -> bool:
    key = dz_market.describe(listing)[0]
    return not key or not pricebook.is_specific(key)


def identify(db: Session, settings: Settings, search: Search, rows: list[Listing], limit: int = SPECS_PER_RUN) -> int:
    """Let the spec model read fresh ads whose product is unclear ("i5 11e génération", CPU only in the
    description), so they can get a price. Each ad is read once. Returns ads read."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    max_age = float(settings.max_ad_age_hours or freshness.FRESH_HOURS)
    todo = []
    for listing in rows:
        if listing.screen_skip or listing.gone_at is not None or listing.is_active is False or listing.dz_price_median_dzd:
            continue
        if (listing.spec_notes or {}).get("model") or (listing.id, "specs") in _failed or not _unknown_product(listing):
            continue
        age = freshness.age_hours(listing, now)
        if (age is not None and age > max_age) or match.hard_fail(search, listing):
            continue
        todo.append((age if age is not None else 1e9, listing))
    todo.sort(key=lambda pair: pair[0])
    for _, listing in todo[:limit]:
        item: dict[str, Any] = {"steps": {name: "pending" for name in STEPS}, "notes": {}, "verdict": None}
        _specs_step(db, settings, listing, search, item)
    return min(len(todo), limit)


def run_for(db: Session, settings: Settings, search: Search, listings: list[Listing], limit: int = PRICES_PER_RUN) -> int:
    """Before Telegram alerts: identify unclear ads, one price request per new product, then maths for every ad
    of the search (fresh ads left unpriced by earlier scans included). Returns price requests made."""
    if not dz_market.api_key(settings):
        return 0
    seen = {listing.id for listing in listings}
    rows = list(listings) + [listing for listing in _search_rows(db, search) if listing.id not in seen]
    fill_from_book(db, settings, rows, search)
    try:
        identify(db, settings, search, rows)
    except Exception as exc:  # the price step still runs for ads that are already clear
        db.rollback()
        print(f"[enrich] spec step failed: {type(exc).__name__}: {exc}")
    chosen = _freshest_needing_ai(rows, search, settings, limit, full=False)
    for listing in chosen:
        item: dict[str, Any] = {"steps": {name: "pending" for name in STEPS}, "notes": {}, "verdict": None}
        enrich_listing(db, settings, listing, search, item, full=False)
    fill_from_book(db, settings, rows, search)
    return len(chosen)


def _merge_specs(listing: Listing, found: dict[str, Any]) -> list[str]:
    """Fill only the specs the regex left empty; return the fields that were set."""
    specs = dict(listing.specs or {})
    confidence = dict(listing.spec_confidence or {})
    method = dict(listing.spec_method or {})
    filled = []
    for field, value in found.items():
        if specs.get(field):
            continue
        try:
            if field in ("ram_gb", "storage_gb"):
                value = int(float(value))
            elif field == "screen_inches":
                value = round(float(value), 1)
            else:
                value = str(value).strip()
        except (TypeError, ValueError):
            continue
        if not value:
            continue
        specs[field] = value
        confidence[field] = "medium"
        method[field] = "llm"
        filled.append(field)
    if specs.get("cpu") and not specs.get("cpu_family"):
        specs["cpu_family"] = cpu_db.family_of(specs["cpu"])
    listing.specs, listing.spec_confidence, listing.spec_method = specs, confidence, method
    return filled


def _specs_step(db: Session, settings: Settings, listing: Listing, search: Optional[Search], item: dict[str, Any]) -> None:
    """The spec model fills missing specs and writes a description; the ad's product key is then rebuilt."""
    item["steps"]["specs"] = "running"
    text = " ".join(part for part in (listing.subject, listing.description) if part)
    try:
        res = llm.extract_specs_detailed(db, settings, text, listing.specs or {})
    except Exception as exc:  # pragma: no cover - defensive
        res = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "model": settings.spec_model}
    if res["ok"]:
        filled = _merge_specs(listing, res["specs"])
        listing.ai_description = res["description"] or listing.ai_description or ""
        listing.spec_notes = {"model": res["model"], "at": _iso(), "evidence": res["evidence"], "filled": filled}
        db.commit()
        analyze.analyze_listing(db, settings, listing, search, force=False, use_ai=False)  # refresh keys, match, screen
        db.commit()
        item["steps"]["specs"] = "done"
        item["notes"]["specs"] = f"{res['model']} filled: {', '.join(filled) or 'nothing new'}"
    else:
        _failed.add((listing.id, "specs"))
        item["steps"]["specs"] = "error"
        item["notes"]["specs"] = res["error"]


def enrich_listing(
    db: Session, settings: Settings, listing: Listing, search: Optional[Search], item: dict[str, Any], full: bool = True
) -> None:
    """Run the missing steps for one ad, recording each step's outcome in ``item`` (never raises)."""
    todo = needs(listing, full)

    def step(name: str, state: str, message: str = "") -> None:
        item["steps"][name] = state
        if message:
            item["notes"][name] = message

    # 1. specs + description, by the free model
    if "specs" in todo:
        _specs_step(db, settings, listing, search, item)
    else:
        step("specs", "skipped", "already done" if full else "not needed for the price")

    # 2. Algerian price
    if not listing.dz_price_median_dzd:
        step("price", "running")
        if not dz_market.available(settings):
            step("price", "error", "Algerian price search is switched off or there is no OpenRouter key")
        else:
            try:
                analyze.apply_dz_comparison(db, settings, listing)
                db.commit()
            except Exception as exc:  # pragma: no cover - defensive
                db.rollback()
                step("price", "error", f"{type(exc).__name__}: {exc}")
            if listing.dz_price_median_dzd:
                step("price", "done", f"{settings.gemini_model}: {listing.dz_price_median_dzd:,.0f} DA ({listing.dz_confidence or '?'} confidence)")
            elif item["steps"]["price"] != "error":
                if not dz_market.is_temporary_failure(listing):  # out of credit or busy: retry later
                    _failed.add((listing.id, "price"))
                step("price", "error", dz_market.last_error(db, listing) or "no Algerian price found")
    else:
        step("price", "skipped", "price already known")

    if not full:  # the verdict comes from the numbers, with no model call
        if verdict.apply_math(settings, listing):
            db.commit()
            item["verdict"] = listing.ai_verdict_label
            step("verdict", "done", f"by maths: {listing.ai_verdict_label}")
        else:
            step("verdict", "skipped", "needs an Algerian price first")
        return

    # 3. verdict, by Haiku
    if (listing.ai_verdict or {}).get("source") != "ai":
        if listing.dz_price_median_dzd:
            step("verdict", "running")
            try:
                result = verdict.apply(db, settings, listing)
                item["verdict"] = result["verdict"]
                if result.get("source") == "ai":
                    step("verdict", "done", f"{result['model']}: {result['verdict']}")
                else:
                    _failed.add((listing.id, "verdict"))
                    step("verdict", "error", f"{settings.verdict_model} did not answer, rule-based verdict used: {result['verdict']}")
            except Exception as exc:
                db.rollback()
                _failed.add((listing.id, "verdict"))
                step("verdict", "error", f"{type(exc).__name__}: {exc}")
        else:
            step("verdict", "skipped", "needs an Algerian price first")
    else:
        item["verdict"] = listing.ai_verdict_label
        step("verdict", "skipped", "verdict already written")


def _run(job: dict[str, Any], session_factory: Any = None) -> None:
    from ..db import SessionLocal
    from ..api.helpers import get_settings

    try:
        with (session_factory or SessionLocal)() as db:
            settings = get_settings(db)
            search = db.get(Search, job["search_id"])
            for item in job["items"]:
                listing = db.get(Listing, item["id"])
                if listing is not None:
                    enrich_listing(db, settings, listing, search, item, full=job["full"])
                item["finished"] = True
            if search is not None:
                fill_from_book(db, settings, _search_rows(db, search), search)  # the new prices reach every ad
    except Exception as exc:  # the page shows the error instead of a silent stall
        job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        job["running"] = False
        job["finished_at"] = _iso()


def start(
    db: Session,
    search: Search,
    settings: Settings,
    auto: bool = True,
    limit: int = TOP_N,
    inline: bool = False,
    session_factory: Any = None,
) -> dict[str, Any]:
    """Start (or report) the AI batch of a search. Returns the job summary."""
    with _lock:
        current = _jobs.get(search.id)
        if current and current["running"]:
            return {"started": False, "reason": "already_running", **summary(search.id)}
        if auto and time.time() - _last_auto.get(search.id, 0) < COOLDOWN_S:
            return {"started": False, "reason": "cooldown", **summary(search.id)}
        if not dz_market.api_key(settings):
            return {"started": False, "reason": "no_key", **summary(search.id)}

        if not auto:
            _failed.clear()  # the "Run AI now" button retries what failed before
        full = not auto  # page open: one price per product; "Run AI" button: all three steps
        listings = pick(db, search, settings, limit, full)
        if not listings:
            return {"started": False, "reason": "nothing_to_do", **summary(search.id)}
        if auto:
            _last_auto[search.id] = time.time()
        job = {
            "search_id": search.id,
            "running": True,
            "full": full,
            "started_at": _iso(),
            "finished_at": None,
            "error": "",
            "models": {"specs": settings.spec_model, "price": settings.gemini_model, "verdict": settings.verdict_model},
            "items": [
                {
                    "id": l.id,
                    "subject": (l.subject or "")[:90],
                    "steps": {name: "pending" for name in STEPS},
                    "notes": {},
                    "verdict": None,
                    "finished": False,
                }
                for l in listings
            ],
        }
        _jobs[search.id] = job

    if inline:
        _run(job, session_factory)
    else:
        threading.Thread(target=_run, args=(job, session_factory), daemon=True, name=f"enrich-{search.id}").start()
    return {"started": True, "reason": "", **summary(search.id)}


def summary(search_id: int) -> dict[str, Any]:
    job = _jobs.get(search_id)
    if not job:
        return {"running": False, "items": [], "models": {}, "error": "", "started_at": None, "finished_at": None}
    return {k: job[k] for k in ("running", "items", "models", "error", "started_at", "finished_at")}
