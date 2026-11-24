import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:  # read-only filesystem (serverless)
    pass

load_dotenv(BASE_DIR / ".env")

# True when running as a serverless function (Vercel): no background threads, no local disk.
SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("SERVERLESS"))


def _normalize_db_url(url: str) -> str:
    """Accept the postgres:// URLs Supabase hands out and use the psycopg 3 driver."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}")
# Built frontend served by the backend itself (Docker / single-process deployments).
STATIC_DIR = Path(os.getenv("STATIC_DIR") or PROJECT_ROOT / "frontend" / "dist")
# Shared password protecting the UI/API once it is public. Empty = no login (local use).
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
# false on any second copy (e.g. a dev PC): two schedulers would fight over Telegram and alert twice
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
# Secret for the /api/cron/tick endpoint (sent as "Authorization: Bearer <secret>").
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
# Base URL of the web UI, used for "Open in app" links in Telegram alerts.
APP_URL = os.getenv("APP_URL", "http://localhost:5173").strip().rstrip("/")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()
FRONTEND_ORIGINS = [o.strip() for o in os.getenv(
    "FRONTEND_ORIGINS",
    f"{FRONTEND_ORIGIN},http://127.0.0.1:5173,http://localhost:3000",
).split(",") if o.strip()]

LEBONCOIN_BASE_URL = "https://www.leboncoin.fr/recherche"
JINA_READER = "https://r.jina.ai/"
JINA_HEADERS = {"x-return-format": "html", "Accept": "*/*"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 120

# Fetch strategies tried in order: "reader" (r.jina.ai) and/or "direct" (browser-like request).
SCRAPE_STRATEGIES = [x.strip() for x in os.getenv("SCRAPE_STRATEGIES", "reader,direct").split(",") if x.strip() in ("reader", "direct")] or ["reader"]
# Optional residential/rotating proxy for the scraper, e.g. http://user:pass@host:port
PROXY_URL = os.getenv("PROXY_URL", "").strip()
