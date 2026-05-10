# 🖥️ MacBook Deal Intelligence System

An AI-powered deal monitoring system that tracks high-value used Apple Silicon MacBook Pro listings on eBay, filters scams, scores deals, and sends curated Telegram alerts.

---

## Features

- 📡 **RSS-first monitoring** — discovers only new eBay listings, minimizing Firecrawl credit usage
- 🤖 **AI filtering** — OpenAI-powered scam detection and workstation suitability scoring  
- 📊 **Deal scoring** — ranks by RAM, chip tier, seller trust, battery health, and price efficiency
- 🔔 **Telegram alerts** — instant notifications for high-value deals above configurable threshold
- 🗄️ **Persistent storage** — SQLite (dev) / PostgreSQL (prod) with full history
- 🔌 **REST API** — FastAPI endpoints to query listings, trigger runs, and view stats

---

## Quick Start

### 1. Clone & install

```bash
cd MacbookEbayScraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
| Key | Where to get |
|-----|-------------|
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://firecrawl.dev) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/botfather) on Telegram |
| `TELEGRAM_CHAT_ID` | Send `/start` to [@userinfobot](https://t.me/userinfobot) |

### 3. Create data directory & run

```bash
mkdir -p data
uvicorn app.main:app --reload
```

### 4. Trigger a manual pipeline run

```bash
curl -X POST http://localhost:8000/scrape/run
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/listings` | All listings (paginated, filterable) |
| `GET` | `/listings/{id}` | Single listing detail |
| `GET` | `/top-deals` | Top N listings by deal score |
| `GET` | `/stats` | Pipeline statistics |
| `POST` | `/scrape/run` | Manually trigger pipeline |

---

## Deal Scoring

Scores are 0–10, weighted as:

| Factor | Weight |
|--------|--------|
| RAM (64GB = best) | 40 pts |
| Chip tier (Max > Pro > Base) | 35 pts |
| Seller rating + returns | 25 pts |
| Battery health | 15 pts |
| Condition | 10 pts |
| Price penalty | −variable |

---

## Architecture

```
eBay RSS Feeds
     ↓
New Listing Detection (RSS monitor)
     ↓
Firecrawl Extraction (per new listing)
     ↓
Structured Data Parser (regex + heuristics)
     ↓
AI Filter (OpenAI gpt-4o-mini)
     ↓
Deal Scoring Engine
     ↓
SQLite / PostgreSQL
     ↓
Telegram Notification (if score ≥ threshold)
     ↓
FastAPI REST API
```

---

## Project Structure

```
app/
├── main.py              # FastAPI entrypoint + lifespan
├── config.py            # Centralized settings (pydantic-settings)
├── scheduler.py         # APScheduler (runs pipeline every N hours)
├── api/routes.py        # REST endpoints
├── ai/
│   ├── ai_filter.py     # OpenAI scam/quality classification
│   └── prompts.py       # Prompt templates
├── database/database.py # Async SQLAlchemy engine
├── models/listing.py    # ORM model
├── notifications/
│   └── telegram_notifier.py
├── rss/
│   ├── feed_builder.py  # Builds eBay RSS URLs
│   └── rss_monitor.py   # Parses feeds, finds new listings
├── scraper/
│   ├── firecrawl_client.py
│   └── listing_parser.py
├── scoring/deal_ranker.py
└── services/pipeline.py # Main orchestration
```

---

## Configuration Reference

See `.env.example` for all tunables. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEAL_SCORE_THRESHOLD` | `7.0` | Min score for Telegram alert |
| `MAX_PRICE_USD` | `1500.0` | Listings above this are skipped |
| `RUN_INTERVAL_HOURS` | `6` | How often the pipeline runs |
| `ENABLE_AI_FILTER` | `true` | Toggle OpenAI filtering |
| `ENABLE_TELEGRAM` | `true` | Toggle Telegram notifications |
