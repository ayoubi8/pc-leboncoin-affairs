from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import dashboard, imports, listings, searches
from .api import settings as settings_api
from .config import FRONTEND_ORIGINS
from .db import init_db
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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

app.include_router(dashboard.router)
app.include_router(searches.router)
app.include_router(listings.router)
app.include_router(settings_api.router)
app.include_router(imports.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "laptop-deal-finder"}
