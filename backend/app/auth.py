"""Optional shared-password login, enabled when APP_PASSWORD is set (public deployments)."""
from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config

COOKIE = "deal_session"
router = APIRouter(prefix="/api/auth", tags=["auth"])

# reachable without a session (health check, login itself, cron has its own secret)
_OPEN_PREFIXES = ("/api/auth/", "/api/cron/")
_OPEN_PATHS = {"/api/health"}


def _token() -> str:
    # Derived from the password, so changing APP_PASSWORD logs everyone out.
    return hmac.new(config.APP_PASSWORD.encode(), b"deal-finder-session", hashlib.sha256).hexdigest()


def is_authenticated(request: Request) -> bool:
    if not config.APP_PASSWORD:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""), _token())


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if (
        config.APP_PASSWORD
        and path.startswith("/api/")
        and path not in _OPEN_PATHS
        and not path.startswith(_OPEN_PREFIXES)
        and not is_authenticated(request)
    ):
        return JSONResponse({"detail": "Login required"}, status_code=401)
    return await call_next(request)


class LoginBody(BaseModel):
    password: str = ""


@router.get("/me")
def me(request: Request) -> dict:
    return {"auth_required": bool(config.APP_PASSWORD), "authenticated": is_authenticated(request)}


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    if config.APP_PASSWORD and not hmac.compare_digest(body.password, config.APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Wrong password")
    if config.APP_PASSWORD:
        response.set_cookie(
            COOKIE, _token(), httponly=True, samesite="lax", secure=config.SERVERLESS, max_age=60 * 60 * 24 * 30, path="/"
        )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
