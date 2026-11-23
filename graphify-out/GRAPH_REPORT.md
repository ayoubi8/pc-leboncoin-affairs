# Graph Report - pc-leboncoin-affairs  (2026-11-23)

## Corpus Check
- 102 files · ~55,832 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1015 nodes · 2452 edges · 56 communities (55 shown, 1 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 43 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d09e89fa`
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
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 45 edges
2. `Listing` - 42 edges
3. `get_settings()` - 37 edges
4. `Search` - 35 edges
5. `cn()` - 26 edges
6. `Sink` - 20 edges
7. `FastAPI` - 19 edges
8. `upsert_ads()` - 18 edges
9. `compilerOptions` - 18 edges
10. `Session` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_leboncoin_detects_reader_captcha()` --calls--> `detect_block()`  [INFERRED]
  backend/tests/test_core.py → backend/app/scraping/leboncoin.py
- `Settings` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `DzPrice` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `ImportBatch` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py
- `Listing` --uses--> `Base`  [INFERRED]
  backend/app/models.py → backend/app/db.py

## Import Cycles
- 1-file cycle: `backend/app/main.py -> backend/app/main.py`
- 1-file cycle: `backend/app/api/ops.py -> backend/app/api/ops.py`
- 1-file cycle: `backend/app/scheduler.py -> backend/app/scheduler.py`
- 1-file cycle: `backend/app/api/helpers.py -> backend/app/api/helpers.py`
- 1-file cycle: `backend/app/models.py -> backend/app/models.py`
- 1-file cycle: `backend/app/intelligence/freshness.py -> backend/app/intelligence/freshness.py`
- 1-file cycle: `backend/app/intelligence/dz_market.py -> backend/app/intelligence/dz_market.py`
- 1-file cycle: `backend/app/intelligence/verdict.py -> backend/app/intelligence/verdict.py`
- 1-file cycle: `backend/app/notify/pipeline.py -> backend/app/notify/pipeline.py`
- 1-file cycle: `backend/app/notify/system.py -> backend/app/notify/system.py`
- 1-file cycle: `backend/app/notify/deals.py -> backend/app/notify/deals.py`
- 2-file cycle: `backend/app/api/searches.py -> backend/app/main.py -> backend/app/api/searches.py`
- 2-file cycle: `backend/app/api/listings.py -> backend/app/main.py -> backend/app/api/listings.py`
- 2-file cycle: `backend/app/api/ops.py -> backend/app/main.py -> backend/app/api/ops.py`
- 2-file cycle: `backend/app/api/imports.py -> backend/app/main.py -> backend/app/api/imports.py`
- 2-file cycle: `backend/app/api/settings.py -> backend/app/main.py -> backend/app/api/settings.py`
- 2-file cycle: `backend/app/api/dashboard.py -> backend/app/main.py -> backend/app/api/dashboard.py`
- 2-file cycle: `backend/app/api/cron.py -> backend/app/main.py -> backend/app/api/cron.py`
- 2-file cycle: `backend/app/auth.py -> backend/app/main.py -> backend/app/auth.py`

## Communities (56 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.19
Nodes (21): ageLabel(), freshnessTone(), ListingCard(), ScoreRing(), CONDITION_LABELS, conditionLabel(), dateShort(), DEAL_STYLES (+13 more)

### Community 1 - "Community 1"
Cohesion: 0.16
Nodes (27): alert_now(), create_search(), delete_search(), enrich_status(), export_csv(), _get_search(), _latest_run_id(), list_runs() (+19 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (42): Listing, Search, FastAPI, _ad(), test_fresh_beats_old_and_sold_wording_hurts(), test_gone_ad_scores_zero(), test_recent_bump_keeps_an_old_ad_alive(), _client() (+34 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (26): Any, Listing, Search, Any, Search, compute_match(), _contains(), hard_fail() (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (40): Any, Listing, Search, Session, Settings, Any, Any, datetime (+32 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (35): Any, Session, Settings, Any, datetime, Session, Settings, Any (+27 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (22): LivePanel(), LivePill(), liveSummary(), ProgressBar(), RunningScan(), Tone, TONE_DOT, EmptyState() (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (10): Any, Listing, attributes(), Cheap, free checks that run BEFORE any paid lookup.  Reads the structured fiel, True when the price is so far below the reference it is probably a scam or a bro, yes | no | unknown, from Leboncoin's own fields first, then the ad text., Return {"skip": bool, "reasons": [...], "flags": [...], "ship_ok": str, "old_pri, scam_price() (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (28): Any, Session, RuntimeError, _attr_map(), build_url(), check_ad_status(), classify_ad_page(), detect_block() (+20 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (34): DzPrice, Cached Algerian market price per laptop configuration (one Gemini lookup each)., Any, datetime, DzPrice, Listing, Session, Settings (+26 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (25): dependencies, clsx, lucide-react, react, react-dom, react-router-dom, recharts, tailwind-merge (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (31): Any, datetime, Listing, Search, Session, Settings, _check_online(), deal_card() (+23 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (23): LlmCache, Any, Session, Settings, Any, Listing, Session, Settings (+15 more)

### Community 13 - "Community 13"
Cohesion: 0.16
Nodes (23): act_now(), delete_price(), edit_price(), _listing(), live(), ManualPrice, _now(), pipeline_board() (+15 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleDetection, moduleResolution (+11 more)

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (16): dashboard(), listing_card(), run_out(), search_out(), search_result_count(), DashboardKPIs, ListingCard, Session (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (16): Any, datetime, Listing, age_hours(), apply(), compute(), _curve(), _last_sunday() (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (17): Acceptance criteria (MVP), Architecture, Change log, Current state, Decisions (locked with user), Laptop Deal Finder - Progress & Task Tracker, Phase 0 - Foundation, Phase 1 - Collection (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.27
Nodes (22): SearchListing, _db(), _linked(), _listing(), _paris(), Scans do no AI by themselves; the alert step prices and judges the freshest new, Leboncoin-style timestamp (Paris time, UTC+1 in winter) for an ad published `hou, _setup() (+14 more)

### Community 19 - "Community 19"
Cohesion: 0.22
Nodes (6): upload_csv(), get_db(), Session, ImportResult, Copy the local SQLite database into Postgres (Supabase).  Usage (from backend/):, UploadFile

### Community 20 - "Community 20"
Cohesion: 0.15
Nodes (23): Any, Any, _db(), family_of(), label(), lookup(), normalize_cpu(), Map a form value or a CPU family (``i7``, ``ryzen5``, ``apple_m``...) to a vendo (+15 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (24): Dot(), SetupChecklist(), Button(), BUTTON_SIZES, BUTTON_VARIANTS, ButtonSize, ButtonVariant, Card() (+16 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (27): Any, Listing, Any, datetime, Listing, Session, Settings, _bucket() (+19 more)

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (14): Layout(), NAV, THEME_LABEL, THEME_ORDER, ThemeToggle(), ThemeToggleInline(), Toaster(), applyTheme() (+6 more)

### Community 24 - "Community 24"
Cohesion: 0.31
Nodes (9): Base, Negotiation, PriceSnapshot, Run, utcnow(), datetime, DeclarativeBase, test_paris_conversion_winter_and_summer() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (20): BulkNegotiationRequest, DashboardOut, ImportResult, ListingDetail, ListingOut, NegotiationOut, NegotiationRequest, ORMModel (+12 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (32): Endpoint an external scheduler (GitHub Actions, cron-job.org) calls to run due s, tick(), Vercel entry point: exposes the FastAPI app as a serverless function., auth_middleware(), is_authenticated(), login(), LoginBody, logout() (+24 more)

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
Cohesion: 0.22
Nodes (16): get_settings(), mask_key(), _out(), Run the real model calls with the saved key and say what is wrong., Fetch one real results page the way a scan does., Find the chat id of whoever messaged the bot, and save it., read_settings(), telegram_detect() (+8 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (31): REASONS, STEP_LABEL, StepChip(), STEPS, useEnrich(), ActNow, ApiError, Dashboard (+23 more)

### Community 41 - "Community 41"
Cohesion: 0.35
Nodes (14): Any, Listing, Run, Search, Session, Settings, price_changed(), GeneratedQuery (+6 more)

### Community 42 - "Community 42"
Cohesion: 0.18
Nodes (10): Badge(), PriceBookRow, emit(), items, Listener, listeners, toast(), ToastItem (+2 more)

### Community 43 - "Community 43"
Cohesion: 0.24
Nodes (10): end_run(), events(), log(), _now_iso(), _public(), What the backend is doing right now, kept in memory for the live UI.  Nothing, running(), start_run() (+2 more)

### Community 44 - "Community 44"
Cohesion: 0.21
Nodes (9): Any, Settings, Any, Settings, compute(), Algeria import charges on a CIF basis.      ``personal`` follows the occasiona, compute(), estimate_package() (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.22
Nodes (25): Any, Listing, Search, Session, Settings, enrich_listing(), fill_from_book(), _freshest_needing_ai() (+17 more)

### Community 46 - "Community 46"
Cohesion: 0.46
Nodes (7): Any, Listing, Session, compute_market(), market_payload(), _percentile(), _prices_for()

### Community 47 - "Community 47"
Cohesion: 0.17
Nodes (22): best_deals(), bulk_negotiation(), create_negotiation(), generate_verdict(), _get_listing(), _kind(), quote(), Listings with an AI verdict that are still online, ranked by profit weighted by (+14 more)

### Community 48 - "Community 48"
Cohesion: 0.62
Nodes (6): _now(), _search(), _setup(), test_cadence_stays_close_to_interval(), test_due_searches_run_and_others_wait(), test_global_switch_off_runs_nothing()

### Community 50 - "Community 50"
Cohesion: 0.27
Nodes (9): ImportBatch, Any, Search, Session, Settings, ImportBatch, import_csv(), _parse_price() (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.40
Nodes (9): Any, dedupe_ads(), fingerprint(), listing_fingerprint(), _merge(), normalize_text(), Identity of an ad across re-posts: same title + same seller (or same city). Pric, Deduplicate within a single run: list_id, then URL, then fingerprint. (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.50
Nodes (8): Settings, _db(), _listing(), listing_landed(), test_dz_score_uses_landed_vs_algerian_median(), test_failed_lookup_keeps_euro_score(), test_implausible_prices_rejected(), test_no_key_means_no_lookup()

### Community 53 - "Community 53"
Cohesion: 0.71
Nodes (6): _db(), _patch(), _raw(), test_repost_is_linked_and_not_alerted_twice(), test_sold_and_broken_ads_skip_the_paid_lookup(), test_stops_paging_when_page_is_already_known()

### Community 54 - "Community 54"
Cohesion: 0.53
Nodes (4): Settings, convert(), rates(), to_dzd()

### Community 55 - "Community 55"
Cohesion: 0.60
Nodes (5): Any, Settings, quote(), _tariff(), volumetric_kg()

## Knowledge Gaps
- **146 isolated node(s):** `Session`, `DashboardOut`, `Settings`, `Search`, `SearchOut` (+141 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 52` to `Community 2`, `Community 4`, `Community 5`, `Community 9`, `Community 11`, `Community 12`, `Community 15`, `Community 18`, `Community 19`, `Community 22`, `Community 24`, `Community 26`, `Community 27`, `Community 32`, `Community 41`, `Community 44`, `Community 45`, `Community 48`, `Community 50`, `Community 53`, `Community 54`, `Community 55`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `Listing` connect `Community 2` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 9`, `Community 11`, `Community 12`, `Community 13`, `Community 15`, `Community 16`, `Community 18`, `Community 22`, `Community 24`, `Community 26`, `Community 27`, `Community 41`, `Community 45`, `Community 46`, `Community 47`, `Community 52`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Community 32` to `Community 1`, `Community 13`, `Community 45`, `Community 47`, `Community 15`, `Community 19`, `Community 52`, `Community 26`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Settings` (e.g. with `Base` and `_Resp`) actually correct?**
  _`Settings` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Listing` (e.g. with `Base` and `datetime`) actually correct?**
  _`Listing` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Search` (e.g. with `Base` and `datetime`) actually correct?**
  _`Search` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Vercel entry point: exposes the FastAPI app as a serverless function.`, `Endpoint an external scheduler (GitHub Actions, cron-job.org) calls to run due s`, `Session` to the rest of the system?**
  _256 weakly-connected nodes found - possible documentation gaps or missing edges._