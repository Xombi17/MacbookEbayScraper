"""
Pipeline — the main orchestration layer. Optimized for MongoDB.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, time

from rich.console import Console
from rich.table import Table

from app.config import get_settings, SEARCH_QUERIES
from app.database.database import get_db
from app.scraper.discovery import discover_new_listings
from app.scraper.firecrawl_client import get_firecrawl_client
from app.scraper.listing_parser import get_parser
from app.ai.ai_filter import get_ai_filter
from app.scoring.deal_ranker import get_ranker
from app.notifications.telegram_notifier import send_deal_alert

console = Console()


# ── Run Result ────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    run_at: datetime
    feeds_checked: int
    new_listings_found: int
    extracted: int
    filtered_out: int
    stored: int
    notified: int
    errors: int
    duration_seconds: float


# ── Per-listing Processor ─────────────────────────────────────────────────────

async def _process_listing(
    raw: dict,
    db,
    settings,
) -> tuple[bool, bool]:
    """
    Process a single listing end-to-end.
    Returns (stored: bool, notified: bool).
    """
    firecrawl = get_firecrawl_client()
    parser = get_parser()
    ai_filter = get_ai_filter()
    ranker = get_ranker()

    # 1. Extract listing page
    extracted = await firecrawl.extract_listing(raw["url"])
    if not extracted:
        return False, False

    # 2. Parse structured data
    listing_data = parser.parse(
        listing_id=raw["id"],
        listing_url=raw["url"],
        markdown=extracted["markdown"],
        metadata=extracted["metadata"],
    )

    # 3. Strict Price Filter
    if listing_data.price and listing_data.price > settings.max_price_usd:
        return False, False

    # 4. AI analysis
    analysis = await ai_filter.analyze(listing_data)

    # 5. Score
    score_breakdown = ranker.score(listing_data, analysis)

    # 6. Build Document
    listing_doc = {
        "_id": listing_data.listing_id,  # Use eBay ID as primary key
        "url": listing_data.listing_url,
        "title": listing_data.title,
        "price": listing_data.price,
        "currency": listing_data.currency,
        "shipping_cost": listing_data.shipping_cost,
        "condition": listing_data.condition,
        "chip": listing_data.chip,
        "ram_gb": listing_data.ram_gb,
        "storage_gb": listing_data.storage_gb,
        "battery_health": listing_data.battery_health,
        "seller_name": listing_data.seller_name,
        "seller_rating": listing_data.seller_rating,
        "image_url": listing_data.image_url,
        "scam_probability": analysis.scam_probability,
        "workstation_suitability": analysis.workstation_suitability,
        "ai_llm_suitability": analysis.ai_llm_suitability,
        "ai_summary": analysis.summary,
        "is_rejected": analysis.is_rejected,
        "rejection_reason": analysis.rejection_reason,
        "deal_score": score_breakdown.normalized,
        "created_at": datetime.now(),
        "is_notified": False
    }

    # 7. Persist
    await db.listings.update_one(
        {"_id": listing_doc["_id"]},
        {"$set": listing_doc},
        upsert=True
    )

    console.print(
        f"  [dim]→[/dim] Stored: [bold]{listing_data.title[:45] if listing_data.title else 'Unknown'}[/bold] "
        f"| Score: [{'green' if score_breakdown.normalized >= settings.deal_score_threshold else 'yellow'}]"
        f"{score_breakdown.normalized:.1f}[/]"
    )

    # 8. Notify if eligible
    notified = False
    if (
        not analysis.is_rejected
        and score_breakdown.normalized >= settings.deal_score_threshold
        and analysis.scam_probability < 0.3
    ):
        notified = await send_deal_alert(listing_doc)
        if notified:
            await db.listings.update_one(
                {"_id": listing_doc["_id"]},
                {"$set": {"is_notified": True}}
            )

    return True, notified


# ── Main Pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline() -> PipelineResult:
    start = datetime.now()
    settings = get_settings()
    db = get_db()

    console.rule("[bold blue]🚀 MacBook Deal Pipeline Starting (MongoDB)[/bold blue]")

    result = PipelineResult(
        run_at=start, feeds_checked=len(SEARCH_QUERIES),
        new_listings_found=0, extracted=0, filtered_out=0,
        stored=0, notified=0, errors=0, duration_seconds=0.0,
    )

    # Check Daily Budget upfront to avoid wasting search credits
    today_start = datetime.combine(start.date(), time.min)
    scraped_today = await db.listings.count_documents({"created_at": {"$gte": today_start}})
    
    if scraped_today >= settings.daily_credit_limit:
        console.print(f"[bold yellow]⚠️ Daily budget reached ({scraped_today}/{settings.daily_credit_limit}). Exiting early to save credits.[/bold yellow]")
        result.duration_seconds = (datetime.now() - start).total_seconds()
        return result

    # Step 1: Discover new listings
    new_listings = await discover_new_listings(db)
    result.new_listings_found = len(new_listings)

    if not new_listings:
        console.print("[dim]No new listings found.[/dim]")
        result.duration_seconds = (datetime.now() - start).total_seconds()
        return result

    # Step 2: Process sequentially
    for raw in new_listings:
        # Check Daily Budget
        today_start = datetime.combine(datetime.now().date(), time.min)
        scraped_today = await db.listings.count_documents({"created_at": {"$gte": today_start}})
        
        if scraped_today >= settings.daily_credit_limit:
            console.print(f"[bold yellow]⚠️ Daily budget reached ({scraped_today}/{settings.daily_credit_limit}).[/bold yellow]")
            break

        try:
            stored, notified = await _process_listing(raw, db, settings)
            if stored:
                result.extracted += 1
                result.stored += 1
            if notified:
                result.notified += 1
        except Exception as exc:
            console.print(f"  [red]✗ Error processing {raw['url']}: {exc}[/red]")
            result.errors += 1

        await asyncio.sleep(1.5)

    result.duration_seconds = (datetime.now() - start).total_seconds()
    result.filtered_out = result.new_listings_found - result.stored

    # Summary Table
    table = Table(title="Pipeline Run Summary", show_header=False, box=None)
    table.add_row("New listings found", str(result.new_listings_found))
    table.add_row("Stored to MongoDB", str(result.stored))
    table.add_row("Telegram alerts sent", str(result.notified))
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    console.print(table)
    console.rule("[bold green]✓ Pipeline Complete[/bold green]")

    return result
