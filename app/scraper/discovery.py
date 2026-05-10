"""
Firecrawl Discovery — Optimized for MongoDB.
Now serves as the primary discovery method to save credits.
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


async def discover_new_listings(db) -> list[dict]:
    """
    Primary discovery using Firecrawl search results.
    Consolidated to burn only 1 credit per run.
    """
    firecrawl = get_firecrawl_client()
    target_queries = SEARCH_QUERIES
    
    console.print(f"\n[bold green]🕵️ Discovering deals natively via Firecrawl for {len(target_queries)} query...[/bold green]")
    
    all_discovered = []
    seen_ids = set()

    for query in target_queries:
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
        console.print(f"  Scanning: [cyan]{search_url}[/cyan]")
        
        try:
            result = await firecrawl.extract_listing(search_url)
            if not result or not result.get("markdown"):
                continue
                
            # Regex to find [Title](URL) patterns
            # eBay listings often look like [Title](URL) in Firecrawl markdown
            matches = re.findall(r"\[([^\]]+)\]\((https://www\.ebay\.com/itm/\d+)[^\)]*\)", result["markdown"])
            
            # If no [Title](URL) found, fallback to just URL search
            if not matches:
                urls = re.findall(r"https://www\.ebay\.com/itm/\d+", result["markdown"])
                matches = [(None, url) for url in urls]

            # Filter matches against DB
            unique_matches = []
            seen_in_run = set()
            for title, url in matches:
                listing_id = _extract_listing_id(url)
                if listing_id and listing_id not in seen_in_run:
                    seen_in_run.add(listing_id)
                    unique_matches.append((title, url, listing_id))
            
            ids_to_check = [m[2] for m in unique_matches]
            existing = await db.listings.find({"_id": {"$in": ids_to_check}}, {"_id": 1}).to_list(length=None)
            existing_ids = {doc["_id"] for doc in existing}
            
            # Find prices in markdown to associate with listings
            # This is a bit fuzzy but helps the AI pre-filter
            price_matches = re.findall(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", result["markdown"])

            count = 0
            for i, (title, url, listing_id) in enumerate(unique_matches):
                if listing_id not in existing_ids and listing_id not in seen_ids:
                    seen_ids.add(listing_id)
                    
                    # Try to find a price near this listing (very rough heuristic)
                    price = price_matches[i] if i < len(price_matches) else None
                    
                    all_discovered.append({
                        "id": listing_id,
                        "url": _normalize_url(url),
                        "title": title.strip() if title else None,
                        "price_str": price,
                        "query": query
                    })
                    count += 1
            
            console.print(f"    → Found [bold]{count}[/bold] new items for query '{query}'")
            
        except Exception as e:
            console.print(f"  [red]✗ Search crawl failed for {query}: {e}[/red]")
            
    return all_discovered
