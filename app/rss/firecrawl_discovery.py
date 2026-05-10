"""
Firecrawl Discovery — Uses Firecrawl to discover new listings from eBay search pages.
This is a fallback for when eBay RSS feeds return 403 Forbidden.
"""

import re
import asyncio
from rich.console import Console
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, SEARCH_QUERIES
from app.scraper.firecrawl_client import get_firecrawl_client
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
    match = _EBAY_ID_RE.search(url)
    if match:
        item_id = match.group(1)
        return f"https://www.ebay.com/itm/{item_id}"
    return url


async def _get_existing_ids(session: AsyncSession) -> set[str]:
    """Return the set of listing IDs already stored in the database."""
    result = await session.execute(select(Listing.id))
    return {row[0] for row in result.fetchall()}


async def discover_via_firecrawl(session: AsyncSession) -> list[dict]:
    """
    Alternative discovery method using Firecrawl to crawl search results.
    """
    firecrawl = get_firecrawl_client()
    
    # We now scan ALL queries to ensure we get M1-M4 Max results
    target_queries = SEARCH_QUERIES
    
    console.print(f"\n[bold yellow]🕵️ Fallback: Discovering via Firecrawl for {len(target_queries)} queries...[/bold yellow]")
    
    all_discovered = []
    seen_ids = set()
    
    # Get existing IDs from DB to avoid re-processing
    existing_ids = await _get_existing_ids(session)

    for query in target_queries:
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
        console.print(f"  Scanning: [cyan]{search_url}[/cyan]")
        
        try:
            # We use 'map' or 'crawl' would be too expensive, let's use 'scrape' 
            # and just extract links from the search result page
            result = await firecrawl.extract_listing(search_url)
            if not result or not result.get("markdown"):
                continue
                
            # Extract all /itm/ links from the markdown
            # [Title](https://www.ebay.com/itm/123456...)
            matches = re.findall(r"https://www\.ebay\.com/itm/\d+", result["markdown"])
            
            count = 0
            for url in matches:
                listing_id = _extract_listing_id(url)
                if listing_id and listing_id not in seen_ids and listing_id not in existing_ids:
                    seen_ids.add(listing_id)
                    all_discovered.append({
                        "id": listing_id,
                        "url": _normalize_url(url),
                        "title": None, # Will be extracted during full scrape
                        "query": query
                    })
                    count += 1
            
            console.print(f"    → Found [bold]{count}[/bold] new items for query '{query}'")
            
        except Exception as e:
            console.print(f"  [red]✗ Search crawl failed for {query}: {e}[/red]")
            
    return all_discovered
