# Laptop Deal Finder - Progress & Task Tracker

> **How to continue in a new chat:** open this file first. Read `## Current state`,
> then `## Task board`. Work top-down. After finishing any task, mark it `[x]`,
> update `## Current state`, and append a line to `## Change log`.

---

## Project goal

Personal (single-user) web app that:

1. Stores reusable search profiles (laptop / GPU).
2. Scrapes Leboncoin through `r.jina.ai` reader (no DataDome bypass) + manual CSV import.
3. Deduplicates across queries and runs, keeps price history, is incremental.
4. Analyzes: spec extraction, market value, price label, hardware match, negotiation advice.
5. Computes Porsay landed cost (EUR + DZD) and Algeria customs.
6. Generates French negotiation messages on demand (LLM optional).
7. Clean 5-page UI with light/dark/system theme.

**Out of scope:** Telegram, Ouedkniss, Facebook, auto-send, auto-buy, SaaS, platform-protection bypass.

---

## Decisions (locked with user)

| Topic | Decision |
|---|---|
| Scraping | `r.jina.ai` reader + CSV import fallback (NOT DataDome bypass) |
| UI language | English, LTR |
| LLM | Optional. Used only for ambiguous extraction + negotiation messages. OpenRouter. Key lives in `backend/.env` only (never committed / never logged) |
| Workflow | Phase-by-phase, tracked in this file so a new chat can resume |
| Porsay | `chargeable = max(actual_kg, L*W*H/5000)`, tariff tiers configurable in Settings |
| Customs | Two modes: `personal` (Algeria note 2723/25 style) and `standard` (CIF + duty + solidarity + VAT) |
| FX | Official EUR->DZD (default 151.2, used by customs) AND parallel (default 276, used by user cost) - both editable |

### Research notes (2026-11)

- **Porsay** (porsay.com/en/pricing): bills the greater of actual vs volumetric weight
  `L-W-H/5000`. Price depends on destination/service; no public grid -> we keep editable tiers.
  Free storage 6 months, then EUR2/day. Duties NOT included.
- **Algeria customs**:
  - Standard: duty by HS code (computers  5%), solidarity contribution 3%,
    VAT 19% on (CIF + duty + solidarity), CIF valued at **official** FX.
  - Personal/occasional (note 2723/25):  50,000 DZD total exemption;
    50,000-100,000 DZD -> 30% flat for personal use; above -> standard regime.
  - Postal/express:  10,000 DZD exempt; 10k-200k DZD new goods -> forfait (70/100/120/160%).
  - We implement `personal` and `standard` modes, all thresholds/rates editable.
- **FX 2026-11-13**: official 1 EUR  151.2 DZD; parallel  276 DZD (Square Port-Said).

---

## Current state

- **Phase in progress:** 5 complete (backend + frontend); next: Phase 6 polish / live CSV check.
- **Last verified:** 2026-11-13 - `compileall` clean, `pytest` 14/14 green, `npm run build` green, live `GET /api/health` OK, live Leboncoin run reports `blocked` cleanly.
- **Known gaps:**
  - Live scrape through `r.jina.ai` is blocked (DataDome/CAPTCHA). Leboncoin now uses the Next.js App Router: the reader's HTML is a client shell without `__NEXT_DATA__`, so use CSV import. No bypass attempted.
  - `scraping/leboncoin.py` parses legacy `__NEXT_DATA__`; if the reader becomes unblocked, App Router flight-data parsing may be needed.
  - `dashboard.active_searches` is a heuristic (`auto_check_enabled or last_run_at`).
  - Bundle is ~814 kB (Recharts) - optional code-splitting via dynamic import.
  - CSV import is covered by a pytest roundtrip; manual browser upload not yet clicked.

---

## Architecture

```
laptop-deal-finder/
""EUR"EUR PROGRESS.md               # this file
""EUR"EUR README.md                 # quick start
""EUR"EUR backend/
"   ""EUR"EUR requirements.txt
"   ""EUR"EUR .env.example / .env   # secrets (gitignored)
"   ""EUR"EUR run.py                # uvicorn entry
"   """EUR"EUR app/
"       ""EUR"EUR main.py           # FastAPI app + CORS + routers + startup
"       ""EUR"EUR config.py         # env + paths
"       ""EUR"EUR db.py             # engine/session/Base
"       ""EUR"EUR models.py         # SQLAlchemy models
"       ""EUR"EUR schemas.py        # Pydantic I/O
"       ""EUR"EUR api/              # routers
"       ""EUR"EUR scraping/         # r.jina.ai + Leboncoin adapter + datadome detection
"       ""EUR"EUR search/           # French query generator + pipeline runner
"       ""EUR"EUR extraction/       # specs regex + cpu_db + llm fallback
"       ""EUR"EUR processing/       # normalization + dedup
"       ""EUR"EUR intelligence/     # match, market value, deal score, negotiation
"       ""EUR"EUR logistics/        # porsay, customs, currency
"       ""EUR"EUR scheduler.py      # APScheduler auto-check
"       """EUR"EUR data/cpu_db.json  # CPU family -> tier/score
""EUR"EUR frontend/
"   ""EUR"EUR package.json / vite.config.ts / index.html
"   """EUR"EUR src/
"       ""EUR"EUR main.tsx / App.tsx / index.css
"       ""EUR"EUR lib/ (api, theme)
"       ""EUR"EUR components/ (Layout, ui/*)
"       """EUR"EUR pages/ (Dashboard, Searches, SearchForm, Results, ListingDetail, Settings)
"""EUR"EUR data/                     # SQLite database
```

Database tables: `settings`, `searches`, `runs`, `listings`, `search_listings`,
`price_snapshots`, `negotiations`, `import_batches`, `llm_cache` (9).

---

## Task board

### Phase 0 - Foundation
- [x] Create folder structure
- [x] `PROGRESS.md`
- [x] `backend/requirements.txt`, `.env.example`, `.gitignore`
- [x] `backend/app/config.py`, `db.py`
- [x] `backend/app/models.py` (9 tables, indexes, unique constraints)
- [x] `backend/app/schemas.py`
- [x] `backend/app/main.py` (CORS, routers, create_all, seed default settings)
- [x] Frontend scaffold (Vite + React + TS + Tailwind v4)
- [x] Theme toggle (light/dark/system, localStorage)
- [x] Layout + sidebar (desktop) / bottom nav (mobile)

### Phase 1 - Collection
- [x] `scraping/leboncoin.py` - r.jina.ai fetch, `__NEXT_DATA__` parse, retries, DataDome detection
- [x] `search/query_generator.py` - French queries from criteria + preview
- [x] `search/runner.py` - pipeline: scrape -> normalize -> dedup -> store -> analyze
- [x] CSV import (`api/imports.py` + service)
- [x] `api/searches.py` - CRUD + run + results + runs + preview + CSV export
- [x] `api/dashboard.py`

### Phase 2 - Cleaning / incremental
- [x] `processing/dedup.py` (list_id -> url -> fingerprint)
- [x] Skip known listings; re-analyze only on price change
- [x] `price_snapshots` on every observed price
- [x] Cache: extraction + LLM + image (DB `llm_cache`)

### Phase 3 - Intelligence
- [x] `extraction/specs.py` - CPU/RAM/storage/GPU/screen + confidence + method
- [x] `extraction/cpu_db.py` + `data/cpu_db.json`
- [x] `extraction/llm.py` - OpenRouter fallback (only when ambiguous)
- [x] `intelligence/match.py` - hardware match score
- [x] `intelligence/market.py` - market value low/median/high + confidence + comparisons
- [x] `intelligence/deal.py` - deal score + label
- [x] `intelligence/negotiation.py` - ask/initial/target/max + FR messages (tone + LLM optional)
- [x] Dynamic quote endpoint (`POST /api/listings/{id}/quote`)

### Phase 4 - Logistics
- [x] `logistics/porsay.py` - volumetric + tiers
- [x] `logistics/customs.py` - personal + standard modes
- [x] `logistics/currency.py` - official/parallel
- [x] Landed cost (EUR + DZD) in listing detail + quote

### Phase 5 - UI
- [x] `/` Dashboard (KPIs, last runs, best deals, alerts)
- [x] `/searches` list + actions
- [x] `/searches/new` + edit page (all optional fields, query preview)
- [x] `/searches/:id/results` (sort, filter, multi-select, bulk bar)
- [x] `/listings/:id` (images, specs+confidence, market value, negotiation, calculator, Porsay, sparkline)
- [x] `/settings`
- [x] Polish: badges, skeleton/loading, toast, responsive

### Phase 6 - Automation
- [x] `scheduler.py` APScheduler jobs from search intervals
- [ ] Dashboard notifications (price changes, failed checks)
- [ ] Perf: indexes, pagination, cache warm

### Verification
- [x] `python -m compileall backend`
- [x] Smoke test extraction + logistics + market locally (`pytest`: 14 passed)
- [x] `npm run build` passes
- [x] Live run against Leboncoin (1 page) works or records DataDome failure cleanly

---

## Acceptance criteria (MVP)

- [ ] Create search with any combination of optional criteria
- [ ] Collect Leboncoin results (or CSV import when blocked)
- [ ] Correct dedup inside a run and across runs
- [ ] New check skips known listings, analyzes only new/changed
- [ ] Market value + price label + negotiation recommendations
- [ ] Dynamic calculator + Porsay landed cost (EUR + DZD)
- [ ] Negotiation messages on demand only (single + bulk)
- [ ] 5 pages + sort/filter/multi-select
- [ ] Working dark/light toggle (persisted)
- [ ] Manual and scheduled checks share one pipeline

---

## Change log

- 2026-11-13 - Project created; research on Porsay/customs/FX recorded; scaffold started.
- 2026-11-13 - Backend complete: main/scheduler/run entrypoints; deps installed in `backend/.venv`; `pytest` 11/11; live health check OK. Fixed CPU/GPU/size/condition extraction bugs; removed duplicate index; added `python-multipart`.

- 2026-11-13 - Frontend complete: 6 routes + Settings page, `npm install` (130 packages), `npm run build` green (~814 kB bundle warning from Recharts). Fixed `match.py` CPU-family precedence, real `landed_asc` sort, CSV batch status semantics, and added `llm_key_set` to `GET /api/settings`.
- 2026-11-13 - Live Leboncoin via `r.jina.ai` reports DataDome/CAPTCHA (page now App Router, no `__NEXT_DATA__`). Added markdown probe + CAPTCHA markers so runs report `blocked` cleanly; use CSV import as the collection path. `pytest` 13/13.

- 2026-11-13 - CSV path verified end-to-end (`pytest`: upload -> import -> results). Fixed missing `listing_card` import in `api/searches.py` (results 500 whenever rows existed) and price parsing for `EUR`/non-breaking spaces. `pytest` 14/14.

