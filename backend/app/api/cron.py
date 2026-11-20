"""Endpoint an external scheduler (GitHub Actions, cron-job.org) calls to run due searches."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException

from .. import config
from ..scheduler import check_due_searches

router = APIRouter(prefix="/api/cron", tags=["cron"])

# Vercel functions are capped (see vercel.json maxDuration); stop starting new searches before that.
TICK_BUDGET_SECONDS = 200


@router.api_route("/tick", methods=["GET", "POST"])
def tick(authorization: str = Header(default="")) -> dict:
    if not config.CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    if not hmac.compare_digest(authorization, f"Bearer {config.CRON_SECRET}"):
        raise HTTPException(status_code=401, detail="Bad cron secret")
    return check_due_searches(budget_seconds=TICK_BUDGET_SECONDS)
