# Agent Context

## Stack
- **Runtime**: Python 3.11+ with FastAPI + APScheduler
- **Async**: `asyncio` + `Motor` (async MongoDB driver)
- **Scraping**: Firecrawl SDK (Native search discovery)
- **AI Filtering**: GitHub Models API (`models.inference.ai.azure.com` endpoint with `gh_models_token`)
- **Storage**: MongoDB (configured via `MONGODB_URI`)
- **Notifications**: Telegram bot via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`

- **CI**: GitHub Actions scheduled every 6 hours, commits DB JSON updates back to repo

## Environment Variables
All loaded from `.env` via `pydantic-settings` (case-insensitive). Key vars:

| Variable | Purpose |
|---|---|
| `FIRECRAWL_API_KEY` | Firecrawl API (1 credit per search) |
| `GH_MODELS_TOKEN` | GitHub Models API token |
| `GH_CHAT_MODEL` | Model name (default: gpt-4o) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat to notify |
| `MONGODB_URI` | MongoDB connection string |
| `DEAL_SCORE_THRESHOLD` | Minimum score to send alert |
| `MAX_PRICE_USD` | Price cap filter |
| `RUN_INTERVAL_HOURS` | Scheduler interval |
| `ENABLE_AI_FILTER` | Toggle GitHub Models filtering |
| `ENABLE_TELEGRAM` | Toggle notifications |

| `ADMIN_API_KEY` | FastAPI admin routes |

**Important**: `.env.example` mentions SQLite for development, but `config.py` uses `mongodb_uri` with default `mongodb://localhost:27017`. Do not use SQLite paths.

## Entry Points
- **FastAPI app** (production): `python app/main.py`
- **Pipeline standalone**: `python -c "from app.services.pipeline import run_pipeline; run_pipeline()"` — used in CI
- **API routes**: `app/routes.py` (health, admin stats, manual run trigger)

## Config
All settings in `app/config.py`:
- `SEARCH_QUERIES`: eBay search URLs (MacBook deals)
- Settings load with `case_sensitive=False` — `MONGODB_URI` and `mongodb_uri` both work
- Defaults: interval=6h, AI filter=enabled, deal threshold=50, max price=1000 USD

## Data Flow
```
Firecrawl Search (1 credit/run)
  -> extract_listing() [async via run_in_executor]
  -> listing_parser.py [regex-based, ListingData dataclass]
  -> GitHub Models AI filter [if ENABLE_AI_FILTER]
  -> score_listing()
  -> Telegram notify [if score >= DEAL_SCORE_THRESHOLD]
  -> MongoDB upsert
  -> commit DB JSON to git (CI only)
```

## Database
- MongoDB collections: `listings`, `pipeline_runs`
- Schema auto-created on startup via Motor
- `database.py` exports `init_db()`, `get_db()` — both are async

## Scraping Discovery
- **Primary**: Firecrawl optimized search (1 credit) → parsed URLs → Firecrawl extract (1 credit per listing)
- Firecrawl client has retry logic with exponential backoff

## AI Filtering
- Uses `openai` library with `api_key=gh_models_token` and `base_url=https://models.inference.ai.azure.com`
- System prompt in `listing_parser.py` defines MacBook deal criteria
- Fallback: skip if AI filter fails (logs warning, continues without scoring)

## Scheduler
- APScheduler `AsyncIOScheduler` in `scheduler.py`
- Starts/stops with FastAPI lifespan
- Manual trigger via POST to `/run-pipeline` (requires `ADMIN_API_KEY`)

## No Existing Docs
This repo had no AGENTS.md or CLAUDE.md previously.

## Critical Quirks
- Firecrawl is credit-limited — be aware when debugging scraping loops
- AI filter is optional (`ENABLE_AI_FILTER`) — pipeline still runs without it
- CI commits DB JSON back to repo — avoid manual DB file edits
- Settings are case-insensitive for env vars