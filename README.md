#  MacBook Deal Intelligence System

A production-grade AI-powered monitoring system that automates the discovery, filtering, and scoring of high-value Apple Silicon MacBook Pro deals.

## 🚀 Overview

This system monitors eBay for "Workstation-Grade" MacBooks (M1 Max to M5 Max). It uses **Firecrawl** for stealth extraction, **GitHub Models (GPT-4o)** for intelligent scam detection, and a **Weighted Scoring Engine** to find the absolute best price-to-performance deals.

### Key Features
- **Intelligent Discovery:** Prioritizes M5/M4/M3 Max models.
- **Scam Protection:** AI-driven detection of MDM locks, iCloud locks, and "For Parts" listings.
- **Credit Budgeting:** Hard limit of 50 Firecrawl credits per day to keep costs low.
- **Automated Alerts:** Instant Telegram notifications for deals scoring ≥ 7.0/10.
- **Cloud Native:** Built-in GitHub Actions CI/CD for 24/7 automated hunting.

---

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python 3.12+)
- **Scraping:** [Firecrawl](https://firecrawl.dev) (Playwright-based stealth extraction)
- **AI:** [GitHub Models](https://github.com/marketplace/models) (GPT-4o)
- **Database:** SQLAlchemy + SQLite (with automated GitHub persistence)
- **Notifications:** Telegram Bot API

---

## ☁️ Cloudflare Worker (RSS Proxy)

To bypass eBay's "403 Forbidden" blocks on RSS feeds, you can deploy a simple Cloudflare Worker to act as a proxy.

### Worker Code (`index.js`)
```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get("url");
    if (!targetUrl) return new Response("Missing url param", { status: 400 });

    const response = await fetch(targetUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml"
      }
    });
    return new Response(response.body, {
      headers: { "Content-Type": "application/rss+xml" }
    });
  }
};
```

---

## ⚙️ Setup & Deployment

### 1. Environment Variables (`.env`)
```bash
FIRECRAWL_API_KEY=your_key
GITHUB_TOKEN=your_pat
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_id
DAILY_CREDIT_LIMIT=50
MAX_PRICE_USD=1500
```

### 2. GitHub Actions (CI/CD)
1. Push this repo to GitHub.
2. Go to **Settings > Secrets > Actions**.
3. Add the keys above as Repository Secrets.
4. The pipeline will automatically run every 6 hours and commit findings back to the `data/deals.db`.

### 3. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload

# Trigger manual scrape
curl -X POST http://localhost:8000/scrape/run
```

---

## 📊 Scoring Heuristics
- **RAM (40%):** Massive bonus for 64GB/128GB unified memory.
- **Chip (30%):** Weighting for M1 Max -> M5 Max tiers.
- **Seller (20%):** Penalty for ratings < 98%.
- **Condition (10%):** Bonus for Refurbished/Excellent condition.

---

## 📜 License
MIT
