from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from . import auth
from .api import cron, dashboard, imports, listings, ops, searches
from .api import settings as settings_api
from .config import FRONTEND_ORIGINS, SERVERLESS, STATIC_DIR
from .db import init_db
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not SERVERLESS:  # on Vercel the cron endpoint drives the schedule instead
        start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Laptop Deal Finder", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth.auth_middleware)
app.include_router(auth.router)
app.include_router(cron.router)
app.include_router(dashboard.router)
app.include_router(searches.router)
app.include_router(listings.router)
app.include_router(ops.router)
app.include_router(settings_api.router)
app.include_router(imports.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "laptop-deal-finder"}


if SERVERLESS:
    # Serverless hosts may not run ASGI lifespan events, so prepare the database at import.
    try:
        init_db()
    except Exception as exc:  # surfaced through /api/health and the logs
        print(f"[startup] init_db failed: {type(exc).__name__}: {exc}")


if not SERVERLESS and (STATIC_DIR / "index.html").is_file():
    # One-process deployment (Docker): serve the built React app, falling back to index.html
    # for client-side routes. Registered last so every /api route wins.
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = (STATIC_DIR / path).resolve()
        if path and target.is_file() and STATIC_DIR.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
