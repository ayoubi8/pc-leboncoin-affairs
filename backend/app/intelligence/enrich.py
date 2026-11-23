"""On-demand AI for the top ads of the Hot deals / Fresh ads views.

Scans never call a model. When a Results page is opened on "Hot deals" or "Fresh ads", the first
``TOP_N`` ads that still need it go through three steps, one after the other:

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
from . import analyze, dz_market, freshness, match, verdict

TOP_N = 5
COOLDOWN_S = 15 * 60  # automatic runs on page open: at most one batch per search every 15 minutes
STEPS = ("specs", "price", "verdict")

_jobs: dict[int, dict[str, Any]] = {}
_last_auto: dict[int, float] = {}
_failed: set[tuple[int, str]] = set()  # (listing id, step) that failed: not retried automatically
_lock = threading.Lock()


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def needs(listing: Listing) -> list[str]:
    """Steps this ad still lacks (an AI verdict replaces a rule-based one)."""
    todo = []
    if not (listing.spec_notes or {}).get("model"):
        todo.append("specs")
    if not listing.dz_price_median_dzd:
        todo.append("price")
    if (listing.ai_verdict or {}).get("source") != "ai":
        todo.append("verdict")
    return [step for step in todo if (listing.id, step) not in _failed]


def _freshest_needing_ai(rows: list[Listing], search: Search, settings: Settings, limit: int) -> list[Listing]:
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
        if not needs(listing):
            continue
        candidates.append((age if age is not None else 1e9, listing))
    candidates.sort(key=lambda pair: pair[0])
    return [listing for _, listing in candidates[:limit]]


def pick(db: Session, search: Search, settings: Settings, limit: int = TOP_N) -> list[Listing]:
    """The freshest ads of the search (same ones the Fresh view lists) that still need AI."""
    rows = db.execute(
        select(Listing).join(SearchListing, SearchListing.listing_id == Listing.id).where(SearchListing.search_id == search.id)
    ).scalars().all()
    return _freshest_needing_ai(rows, search, settings, limit)


def run_for(db: Session, settings: Settings, search: Search, listings: list[Listing], limit: int = TOP_N) -> int:
    """Price and judge the freshest of ``listings`` right now (used before Telegram alerts). Returns how many ran."""
    if not dz_market.api_key(settings):
        return 0
    chosen = _freshest_needing_ai(listings, search, settings, limit)
    for listing in chosen:
        item: dict[str, Any] = {"steps": {name: "pending" for name in STEPS}, "notes": {}, "verdict": None}
        enrich_listing(db, settings, listing, search, item)
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


def enrich_listing(db: Session, settings: Settings, listing: Listing, search: Optional[Search], item: dict[str, Any]) -> None:
    """Run the missing steps for one ad, recording each step's outcome in ``item`` (never raises)."""
    todo = needs(listing)

    def step(name: str, state: str, message: str = "") -> None:
        item["steps"][name] = state
        if message:
            item["notes"][name] = message

    # 1. specs + description, by the free model
    if "specs" in todo:
        step("specs", "running")
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
            step("specs", "done", f"{res['model']} filled: {', '.join(filled) or 'nothing new'}")
        else:
            _failed.add((listing.id, "specs"))
            step("specs", "error", res["error"])
    else:
        step("specs", "skipped", "already done")

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
                _failed.add((listing.id, "price"))
                step("price", "error", dz_market.last_error(db, listing) or "no Algerian price found")
    else:
        step("price", "skipped", "price already known")

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
                    enrich_listing(db, settings, listing, search, item)
                item["finished"] = True
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
        listings = pick(db, search, settings, limit)
        if not listings:
            return {"started": False, "reason": "nothing_to_do", **summary(search.id)}
        if auto:
            _last_auto[search.id] = time.time()
        job = {
            "search_id": search.id,
            "running": True,
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
