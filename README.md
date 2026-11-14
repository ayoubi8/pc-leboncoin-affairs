# Laptop Deal Finder (Leboncoin)

Personal tool: saved searches, Leboncoin collection through `r.jina.ai`, spec/market/negotiation analysis, Porsay shipping + Algerian customs costs, and French negotiation messages.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite, APScheduler (`backend/`)
- Frontend: React 19, Vite 6, Tailwind v4, TanStack Query, Recharts (`frontend/`)

## Setup (Windows, PowerShell)

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # fill OPENROUTER_API_KEY only if you use the LLM features
.\run.py                      # http://127.0.0.1:8000  (docs at /docs)

# Frontend (second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Notes

- Leboncoin is protected by DataDome; live collection often returns `blocked`. Use **Import CSV** on a search's Results page as the reliable path.
- Never commit `backend/.env` or `data/*.db` (both are gitignored).
- Project state and roadmap: see `PROGRESS.md`.
