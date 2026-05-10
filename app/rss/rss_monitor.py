"""
RSS Feed Monitor — discovers new eBay listings without scraping search pages.

Strategy:
1. Parse all configured RSS feeds with feedparser
2. Extract listing IDs from eBay URLs
3. Filter out already-seen IDs (checked against DB)
4. Return only unseen listing IDs + URLs
"""

import re
import asyncio
import feedparser
import httpx
from rich.console import Console
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rss.feed_builder import get_all_feed_urls
from app.models.listing import Listing

console = Console()

# eBay listing ID regex — matches item IDs like /itm/123456789012
_EBAY_ID_RE = re.compile(r"/itm/(\d{10,13})")


def _extract_listing_id(url: str) -> str | None:
    """Extract the eBay item ID from a listing URL."""
    match = _EBAY_ID_RE.search(url)
    return match.group(1) if match else None


def _normalize_url(url: str) -> str:
    """Strip query params to get a clean canonical listing URL."""
    # Keep only the /itm/<id> part to avoid tracker params
    match = _EBAY_ID_RE.search(url)
    if match:
        item_id = match.group(1)
        return f"https://www.ebay.com/itm/{item_id}"
    return url


async def _fetch_feed(client: httpx.AsyncClient, feed_url: str, query: str) -> list[dict]:
    """
    Fetch a single RSS feed and return a list of raw listing dicts.
    Returns empty list on failure (graceful degradation).
    """
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

        console.print(
            f"  [cyan]RSS[/cyan] [{query}] → "
            f"[bold]{len(results)}[/bold] entries"
        )
        return results

    except Exception as exc:
        console.print(
            f"  [yellow]⚠ RSS feed failed for [{query}]: {exc}[/yellow]"
        )
        return []


async def _get_existing_ids(session: AsyncSession) -> set[str]:
    """Return the set of listing IDs already stored in the database."""
    result = await session.execute(select(Listing.id))
    return {row[0] for row in result.fetchall()}


async def discover_new_listings(session: AsyncSession) -> list[dict]:
    """
    Main entry point — fetches all RSS feeds and returns only NEW listings.

    Returns:
        List of dicts: [{"id": str, "url": str, "title": str, "query": str}, ...]
    """
    feeds = get_all_feed_urls()
    console.print(
        f"\n[bold]📡 Fetching {len(feeds)} RSS feeds...[/bold]"
    )

    # Fetch all feeds concurrently
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; MacBookDealBot/1.0)"},
        follow_redirects=True,
    ) as client:
        tasks = [_fetch_feed(client, f["url"], f["query"]) for f in feeds]
        results_nested = await asyncio.gather(*tasks)

    # Flatten and deduplicate by listing ID
    seen_ids: set[str] = set()
    all_listings: list[dict] = []
    for entries in results_nested:
        for entry in entries:
            if entry["id"] not in seen_ids:
                seen_ids.add(entry["id"])
                all_listings.append(entry)

    console.print(
        f"[green]✓[/green] {len(all_listings)} unique listings found across all feeds"
    )

    # Filter out already-processed IDs
    existing_ids = await _get_existing_ids(session)
    new_listings = [l for l in all_listings if l["id"] not in existing_ids]

    # FALLBACK: If RSS failed (common 403) or found nothing, try Firecrawl search crawl
    if not new_listings:
        from app.rss.firecrawl_discovery import discover_via_firecrawl
        new_listings = await discover_via_firecrawl(session)

    console.print(
        f"[bold green]→ {len(new_listings)} NEW listings to process "
        f"({len(all_listings) - len(new_listings)} already seen via RSS)[/bold green]\n"
    )
    return new_listings
