"""What the backend is doing right now, kept in memory for the live UI.

Nothing here is persisted: it describes the running process only. The scanner,
scheduler and Telegram poller report into it, and `/api/live` reads from it.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

_lock = threading.Lock()
_started_at = time.time()

_runs: dict[int, dict[str, Any]] = {}
_events: deque[dict[str, Any]] = deque(maxlen=60)
_ticks: dict[str, Optional[float]] = {"scan_tick": None, "telegram_poll": None}

# Stage -> (label, share of the progress bar that has been earned when the stage STARTS)
STAGES: dict[str, tuple[str, int]] = {
    "starting": ("Starting", 0),
    "fetching": ("Fetching Leboncoin pages", 5),
    "saving": ("Saving and checking freshness", 70),
    "pricing": ("Pricing and judging ads", 70),
    "alerting": ("Sending Telegram alerts", 94),
    "done": ("Finished", 100),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(kind: str, message: str, level: str = "info", **extra: Any) -> None:
    with _lock:
        _events.appendleft({"at": _now_iso(), "kind": kind, "level": level, "message": message, **extra})


def start_run(run_id: int, search_id: int, search_name: str, queries_total: int = 0, trigger: str = "") -> None:
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "search_id": search_id,
            "search_name": search_name,
            "trigger": trigger,
            "stage": "starting",
            "queries_total": queries_total,
            "queries_done": 0,
            "page": 0,
            "ads_found": 0,
            "detail": "",
            "started_at": _now_iso(),
            "_t0": time.time(),
        }
    log("scan", f"Scan started: {search_name} ({trigger or 'auto'})", run_id=run_id, search_id=search_id)


def update_run(run_id: int, **fields: Any) -> None:
    with _lock:
        run = _runs.get(run_id)
        if run:
            run.update(fields)


def end_run(run_id: int, status: str, new_count: int = 0, total: int = 0, error: str = "") -> None:
    with _lock:
        run = _runs.pop(run_id, None)
    if not run:
        return
    name = run["search_name"]
    seconds = round(time.time() - run["_t0"])
    if status == "success":
        log("scan", f"{name}: {total} ads checked, {new_count} new ({seconds}s)", level="success" if new_count else "info", run_id=run_id, search_id=run["search_id"])
    else:
        log("scan", f"{name}: scan {status}" + (f" ({error[:90]})" if error else ""), level="error", run_id=run_id, search_id=run["search_id"])


def _public(run: dict[str, Any]) -> dict[str, Any]:
    label, floor = STAGES.get(run["stage"], (run["stage"], 0))
    total = max(1, run["queries_total"] or 1)
    pct = floor
    if run["stage"] == "fetching":
        # Fetching owns 5 -> 70 %, split evenly across the queries.
        pct = floor + int(65 * min(1.0, run["queries_done"] / total))
    elif run["stage"] == "pricing":
        # Pricing owns 70 -> 94 %, split across the ads being saved.
        pct = floor + int(24 * min(1.0, run.get("ads_done", 0) / max(1, run.get("ads_total", 1))))
    return {
        "run_id": run["run_id"],
        "search_id": run["search_id"],
        "search_name": run["search_name"],
        "trigger": run["trigger"],
        "stage": run["stage"],
        "stage_label": label + (f" · {run['detail']}" if run["detail"] else ""),
        "pct": min(99, pct),
        "queries_done": run["queries_done"],
        "queries_total": run["queries_total"],
        "ads_found": run["ads_found"],
        "started_at": run["started_at"],
        "elapsed_s": round(time.time() - run["_t0"]),
    }


def running() -> list[dict[str, Any]]:
    with _lock:
        return [_public(run) for run in _runs.values()]


def events(limit: int = 30) -> list[dict[str, Any]]:
    with _lock:
        return list(_events)[:limit]


def tick(name: str) -> None:
    with _lock:
        _ticks[name] = time.time()


def last_tick(name: str) -> Optional[float]:
    with _lock:
        return _ticks.get(name)


def uptime_seconds() -> int:
    return int(time.time() - _started_at)
