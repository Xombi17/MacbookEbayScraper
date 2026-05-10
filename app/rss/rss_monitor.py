"""
RSS Feed Monitor — Optimized for MongoDB.
"""

import re
import asyncio
import feedparser
import httpx
from rich.console import Console

from app.rss.feed_builder import get_all_feed_urls

console = Console()

# eBay listing ID regex
_EBAY_ID_RE = re.compile(r"/itm/(\d{10,13})")


def _extract_listing_id(url: str) -> str | None:
    match = _EBAY_ID_RE.search(url)
    return match.group(1) if match else None


def _normalize_url(url: str) -> str:
    match = _EBAY_ID_RE.search(url)
    if match:
        item_id = match.group(1)
        return f"https://www.ebay.com/itm/{item_id}"
    return url


async def _fetch_feed(client: httpx.AsyncClient, feed_url: str, query: str) -> list[dict]:
    try:
        response = await client.get(feed_url, timeout=15.0)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        results = []
        for entry in feed.entries:
            raw_url = entry.get("link", "")
            listing_id = _extract_listing_id(raw_url)
            if not listing_id:
                continue
            results.append({
                "id": listing_id,
                "url": _normalize_url(raw_url),
                "title": entry.get("title", ""),
                "query": query,
            })
        return results
    except Exception as exc:
        console.print(f"  [yellow]⚠ RSS feed failed for [{query}]: {exc}[/yellow]")
        return []


async def discover_new_listings(db) -> list[dict]:
    """
    Main entry point — checks MongoDB to return only NEW listings.
    """
    feeds = get_all_feed_urls()
    console.print(f"\n[bold]📡 Fetching {len(feeds)} RSS feeds...[/bold]")

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; MacBookDealBot/1.0)"},
        follow_redirects=True,
    ) as client:
        tasks = [_fetch_feed(client, f["url"], f["query"]) for f in feeds]
        results_nested = await asyncio.gather(*tasks)

    # Deduplicate
    seen_ids: set[str] = set()
    all_listings: list[dict] = []
    for entries in results_nested:
        for entry in entries:
            if entry["id"] not in seen_ids:
                seen_ids.add(entry["id"])
                all_listings.append(entry)

    if all_listings:
        # Check MongoDB for existing IDs
        listing_ids = [l["id"] for l in all_listings]
        existing = await db.listings.find({"_id": {"$in": listing_ids}}, {"_id": 1}).to_list(length=None)
        existing_ids = {doc["_id"] for doc in existing}
        new_listings = [l for l in all_listings if l["id"] not in existing_ids]
    else:
        new_listings = []

    # Fallback to Firecrawl if RSS is empty or blocked
    if not new_listings:
        from app.rss.firecrawl_discovery import discover_via_firecrawl
        new_listings = await discover_via_firecrawl(db)

    console.print(f"[bold green]→ {len(new_listings)} NEW listings discovered[/bold green]\n")
    return new_listings
