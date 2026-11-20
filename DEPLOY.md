# Deploy on Vercel (free) + Supabase (free)

How it fits together
- **Vercel** serves the React app and runs the FastAPI backend as one serverless function (`api/index.py`).
- **Supabase** holds the data (Postgres). SQLite cannot be used on Vercel.
- **GitHub Actions** calls `/api/cron/tick` every 5 minutes. That runs searches that are due and sends Telegram alerts. (Vercel's own free cron is once a day, too slow.)

## 1. Supabase
1. Create a project. Settings -> Database -> Connection string.
2. Copy the **Transaction pooler** string (port 6543). That is your `DATABASE_URL`.
3. Optional, keep your current data: from `backend/` run
   `python scripts/migrate_to_postgres.py "<direct connection string, port 5432>"`.
   Otherwise the tables are created empty on first start.

## 2. Vercel
1. Push the repo to GitHub, then Vercel -> New Project -> import it. Keep the root directory as the repo root. `vercel.json` handles build and routing.
2. Environment variables:
   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase pooler string |
   | `APP_PASSWORD` | password you will type to open the app (the site is public, so set this) |
   | `CRON_SECRET` | any long random string |
   | `APP_URL` | your Vercel URL, e.g. `https://your-app.vercel.app` |
   | `OPENROUTER_API_KEY` | optional, can also be set in Settings |
3. Deploy. Open the URL, sign in, then Settings: OpenRouter key, Telegram token, Detect chat.

## 3. GitHub Actions cron
Repo -> Settings -> Secrets and variables -> Actions, add:
- `APP_BASE_URL` = your Vercel URL (no trailing slash)
- `CRON_SECRET` = same value as in Vercel

`.github/workflows/cron.yml` then runs every 5 minutes. Test it with Actions -> tick -> Run workflow.

## Limits to know
- A function may run up to 300 s. A manual "Run" of a big search can hit that; the tick stops starting new searches after ~200 s and continues on the next tick.
- GitHub may delay scheduled runs by several minutes. Hourly alerts can arrive a bit late.
- Supabase free pauses a project after a week without activity. The 5-minute tick keeps it active.
- Leboncoin may block Vercel's IPs (DataDome). Check a run's status after deploying.

---

# Docker (one container: API + web UI + scheduler)

```
docker compose up -d --build      # then open http://localhost:8000
```
- Data (SQLite) is kept in the `app-data` volume, so it survives rebuilds. Back it up with `docker run --rm -v <project>_app-data:/d -v "$PWD":/b alpine cp /d/app.db /b/`.
- The in-process scheduler runs as usual (hourly searches, Telegram alerts). No cron needed.
- Optional env (shell or `.env` next to `docker-compose.yml`): `APP_PASSWORD` (set it if the port is reachable from the internet), `OPENROUTER_API_KEY`, `APP_URL`.
- To use Postgres instead of SQLite, uncomment `DATABASE_URL` in the compose file.
- Logs: `docker compose logs -f`. Stop: `docker compose down` (add `-v` to also delete the data).

## Running as a deal machine (recommended: Docker on an always-on PC/VPS)
- Searches can run every 10 / 15 / 30 minutes. After the first run only the newest page is fetched; paging stops as soon as a page is mostly ads already seen.
- Telegram alerts only for ads that are young (default 48 h), shippable, still online (checked against the live ad page just before sending) and profitable even at the full asking price. Each alert carries a ready-to-paste French message.
- Telegram buttons: Contacted / Bought / Skip. Commands: `/paid ID PRICE`, `/sold ID DZD`, `/status`.
- Health: the Dashboard banner and `/status` show scanner blocks and a rejected OpenRouter key; you also get a Telegram alert for each.
- If Leboncoin blocks your IP, set `PROXY_URL` (and keep `SCRAPE_STRATEGIES=reader,direct`).
