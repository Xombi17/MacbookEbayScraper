"""
Firecrawl Discovery — Optimized for MongoDB.
"""

import re
import asyncio
from rich.console import Console
from app.config import get_settings, SEARCH_QUERIES
from app.scraper.firecrawl_client import get_firecrawl_client

console = Console()

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


async def discover_via_firecrawl(db) -> list[dict]:
    """
    Fallback discovery using Firecrawl search results.
    """
    firecrawl = get_firecrawl_client()
    target_queries = SEARCH_QUERIES
    
    console.print(f"\n[bold yellow]🕵️ Fallback: Discovering via Firecrawl for {len(target_queries)} queries...[/bold yellow]")
    
    all_discovered = []
    seen_ids = set()

    for query in target_queries:
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
        console.print(f"  Scanning: [cyan]{search_url}[/cyan]")
        
        try:
            result = await firecrawl.extract_listing(search_url)
            if not result or not result.get("markdown"):
                continue
                
            matches = re.findall(r"https://www\.ebay\.com/itm/\d+", result["markdown"])
            
            # Filter matches against DB
            unique_matches = list(set(matches))
            ids_to_check = [_extract_listing_id(m) for m in unique_matches if _extract_listing_id(m)]
            
            existing = await db.listings.find({"_id": {"$in": ids_to_check}}, {"_id": 1}).to_list(length=None)
            existing_ids = {doc["_id"] for doc in existing}
            
            count = 0
            for url in unique_matches:
                listing_id = _extract_listing_id(url)
                if listing_id and listing_id not in seen_ids and listing_id not in existing_ids:
                    seen_ids.add(listing_id)
                    all_discovered.append({
                        "id": listing_id,
                        "url": _normalize_url(url),
                        "title": None,
                        "query": query
                    })
                    count += 1
            
            console.print(f"    → Found [bold]{count}[/bold] new items for query '{query}'")
            
        except Exception as e:
            console.print(f"  [red]✗ Search crawl failed for {query}: {e}[/red]")
            
    return all_discovered
