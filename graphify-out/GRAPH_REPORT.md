# Graph Report - pc-leboncoin-affairs  (2026-11-20)

## Corpus Check
- 93 files · ~42,817 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 849 nodes · 1940 edges · 41 communities (39 shown, 2 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d49e8ea9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 34 edges
2. `Listing` - 34 edges
3. `get_settings()` - 30 edges
4. `Search` - 25 edges
5. `upsert_ads()` - 18 edges
6. `cn()` - 18 edges
7. `compilerOptions` - 18 edges
8. `Sink` - 16 edges
9. `Base` - 15 edges
10. `FastAPI` - 14 edges

## Surprising Connections (you probably didn't know these)
- `test_leboncoin_detects_reader_captcha()` --calls--> `detect_block()`  [INFERRED]
  backend/tests/test_core.py → backend/app/scraping/leboncoin.py
- `DzPrice` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `Listing` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `LlmCache` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `PriceSnapshot` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py

## Import Cycles
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`
- 1-file cycle: `backend/app/scheduler.py -> backend/app/scheduler.py`
- 1-file cycle: `backend/app/api/helpers.py -> backend/app/api/helpers.py`
- 1-file cycle: `backend/app/models.py -> backend/app/models.py`
- 1-file cycle: `backend/app/intelligence/freshness.py -> backend/app/intelligence/freshness.py`
- 1-file cycle: `backend/app/api/ops.py -> backend/app/api/ops.py`
- 1-file cycle: `backend/app/intelligence/dz_market.py -> backend/app/intelligence/dz_market.py`
- 1-file cycle: `backend/app/intelligence/verdict.py -> backend/app/intelligence/verdict.py`
- 1-file cycle: `backend/app/notify/pipeline.py -> backend/app/notify/pipeline.py`
- 1-file cycle: `backend/app/notify/system.py -> backend/app/notify/system.py`
- 1-file cycle: `backend/app/notify/deals.py -> backend/app/notify/deals.py`
- 2-file cycle: `backend/app/api/listings.py -> backend/app/main.py -> backend/app/api/listings.py`
- 2-file cycle: `backend/app/api/cron.py -> backend/app/main.py -> backend/app/api/cron.py`
- 2-file cycle: `backend/app/api/dashboard.py -> backend/app/main.py -> backend/app/api/dashboard.py`
- 2-file cycle: `backend/app/api/imports.py -> backend/app/main.py -> backend/app/api/imports.py`
- 2-file cycle: `backend/app/api/ops.py -> backend/app/main.py -> backend/app/api/ops.py`
- 2-file cycle: `backend/app/api/searches.py -> backend/app/main.py -> backend/app/api/searches.py`
- 2-file cycle: `backend/app/api/settings.py -> backend/app/main.py -> backend/app/api/settings.py`
- 2-file cycle: `backend/app/auth.py -> backend/app/main.py -> backend/app/auth.py`

## Communities (41 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (77): AuthGate(), ageLabel(), freshnessTone(), ListingCard(), Badge(), Button(), BUTTON_SIZES, BUTTON_VARIANTS (+69 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (78): dashboard(), listing_card(), run_out(), search_out(), search_result_count(), best_deals(), bulk_negotiation(), create_negotiation() (+70 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (47): Base, ImportBatch, Negotiation, Settings, utcnow(), Settings, Any, Settings (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (49): PriceSnapshot, Run, Search, SearchListing, Any, Any, Search, Any (+41 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (33): Any, Listing, Search, Session, Settings, Any, Any, datetime (+25 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (35): Any, Session, Settings, Any, datetime, Session, Settings, Any (+27 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (29): Any, Any, Listing, Search, Any, Listing, _db(), family_of() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (24): Listing, Any, Listing, Session, compute_market(), market_payload(), _percentile(), _prices_for() (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (28): Any, Session, RuntimeError, _attr_map(), build_url(), check_ad_status(), classify_ad_page(), detect_block() (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (26): DzPrice, Cached Algerian market price per laptop configuration (one Gemini lookup each)., Any, datetime, DzPrice, Listing, Session, Settings (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (25): dependencies, clsx, lucide-react, react, react-dom, react-router-dom, recharts, tailwind-merge (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (24): Any, datetime, Listing, Search, Session, Settings, _check_online(), _dzd() (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (21): LlmCache, Any, Session, Settings, Any, Listing, Session, Settings (+13 more)

### Community 13 - "Community 13"
Cohesion: 0.19
Nodes (21): get_settings(), delete_price(), edit_price(), _listing(), ManualPrice, _now(), pipeline_board(), PipelineUpdate (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleDetection, moduleResolution (+11 more)

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (11): Vercel entry point: exposes the FastAPI app as a serverless function., _normalize_db_url(), Accept the postgres:// URLs Supabase hands out and use the psycopg 3 driver., _add_missing_columns(), get_db(), init_db(), Tiny SQLite-friendly migration: add columns new models declare but the table lac, lifespan() (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (16): Any, datetime, Listing, age_hours(), apply(), compute(), _curve(), _last_sunday() (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (17): Acceptance criteria (MVP), Architecture, Change log, Current state, Decisions (locked with user), Laptop Deal Finder - Progress & Task Tracker, Phase 0 - Foundation, Phase 1 - Collection (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.34
Nodes (15): _db(), _listing(), _paris(), Leboncoin-style timestamp (Paris time, UTC+1 in winter) for an ad published `hou, _setup(), Sink, test_ad_that_is_gone_is_not_alerted_and_is_marked(), test_cap_per_run_and_quiet_hours() (+7 more)

### Community 20 - "Community 20"
Cohesion: 0.26
Nodes (14): Any, _attr(), _classify_sizes(), extract_specs(), _find_brand(), _find_condition(), _find_cpu(), _find_gpu() (+6 more)

### Community 21 - "Community 21"
Cohesion: 0.21
Nodes (11): Endpoint an external scheduler (GitHub Actions, cron-job.org) calls to run due s, tick(), check_due_searches(), housekeeping(), poll_telegram(), Re-verify ads we already alerted about (or you acted on) so dead ads drop out of, Cheap upkeep done on every tick; never raises., Button presses and commands, polled often (a few seconds) so taps feel instant. (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.26
Nodes (13): Any, datetime, Listing, Session, Settings, calibrate(), _now(), Deal pipeline (contacted -> bought -> shipped -> sold) and learning from the out (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.27
Nodes (10): NAV, THEME_LABEL, THEME_ORDER, ThemeToggle(), ThemeToggleInline(), applyTheme(), getThemePreference(), systemPrefersDark() (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.33
Nodes (10): mask_key(), _out(), Find the chat id of whoever messaged the bot, and save it., read_settings(), telegram_detect(), telegram_test(), update_settings(), Session (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.33
Nodes (10): auth_middleware(), is_authenticated(), login(), LoginBody, logout(), me(), Optional shared-password login, enabled when APP_PASSWORD is set (public deploym, _token() (+2 more)

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (10): Any, Listing, attributes(), Cheap, free checks that run BEFORE any paid lookup.  Reads the structured fiel, True when the price is so far below the reference it is probably a scam or a bro, yes | no | unknown, from Leboncoin's own fields first, then the ad text., Return {"skip": bool, "reasons": [...], "flags": [...], "ship_ok": str, "old_pri, scam_price() (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.50
Nodes (7): _listing(), _settings(), test_conservative_profit_and_default_discount(), test_model_cannot_beat_the_numbers(), test_no_algerian_price_means_no_numbers(), test_numbers_convert_dzd_to_eur_and_compute_profit(), test_rules_fallback_when_model_down()

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (7): 1. Supabase, 2. Vercel, 3. GitHub Actions cron, Deploy on Vercel (free) + Supabase (free), Docker (one container: API + web UI + scheduler), Limits to know, Running as a deal machine (recommended: Docker on an always-on PC/VPS)

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (7): includeFiles, maxDuration, buildCommand, functions, api/index.py, outputDirectory, rewrites

### Community 30 - "Community 30"
Cohesion: 0.33
Nodes (5): Laptop Deal Finder (Leboncoin), Notes, Setup (Windows, PowerShell), Stack, Tests

### Community 31 - "Community 31"
Cohesion: 0.53
Nodes (4): _client(), test_cron_requires_secret(), test_no_password_means_open_api(), test_password_blocks_api_until_login()

### Community 32 - "Community 32"
Cohesion: 0.50
Nodes (4): upload_csv(), Session, ImportResult, UploadFile

## Knowledge Gaps
- **133 isolated node(s):** `Session`, `DashboardOut`, `Settings`, `Search`, `SearchOut` (+128 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Listing` connect `Community 7` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 15`, `Community 16`, `Community 18`, `Community 21`, `Community 22`, `Community 26`, `Community 27`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 2` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 15`, `Community 18`, `Community 22`, `Community 27`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 13` to `Community 32`, `Community 1`, `Community 2`, `Community 15`, `Community 21`, `Community 24`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Settings` (e.g. with `Base` and `Sink`) actually correct?**
  _`Settings` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Listing` (e.g. with `Base` and `datetime`) actually correct?**
  _`Listing` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Search` (e.g. with `Base` and `datetime`) actually correct?**
  _`Search` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Vercel entry point: exposes the FastAPI app as a serverless function.`, `Endpoint an external scheduler (GitHub Actions, cron-job.org) calls to run due s`, `Session` to the rest of the system?**
  _212 weakly-connected nodes found - possible documentation gaps or missing edges._