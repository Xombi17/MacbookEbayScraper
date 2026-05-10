"""
FastAPI routes — REST API for querying listings and triggering pipeline runs.
Adapted for MongoDB.
"""

import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Security, Request
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database.database import get_db
from app.config import get_settings

router = APIRouter()

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
_LISTING_ID_RE = re.compile(r"^\d{10,13}$")
_scrape_rate_limit_state: dict[str, deque[float]] = defaultdict(deque)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """API key verification for protected endpoints."""
    settings = get_settings()
    if not api_key_header:
        raise HTTPException(status_code=401, detail="Missing API key")
    if not secrets.compare_digest(api_key_header, settings.admin_api_key):
        raise HTTPException(status_code=403, detail="Could not validate API key")
    return api_key_header


# ── Response Schemas ──────────────────────────────────────────────────────────

class ListingOut(BaseModel):
    id: str
    title: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    shipping_cost: Optional[float]
    condition: Optional[str]
    chip: Optional[str]
    ram_gb: Optional[int]
    storage_gb: Optional[int]
    battery_health: Optional[int]
    seller_name: Optional[str]
    seller_rating: Optional[float]
    image_url: Optional[str]
    url: str
    deal_score: Optional[float]
    ai_summary: Optional[str]
    scam_probability: Optional[float]
    is_rejected: bool
    rejection_reason: Optional[str]
    is_notified: bool
    created_at: Optional[datetime]


class StatsOut(BaseModel):
    total_listings: int
    total_notified: int
    total_rejected: int
    avg_deal_score: Optional[float]
    avg_price: Optional[float]
    top_score: Optional[float]


class RunResponse(BaseModel):
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/listings", response_model=list[ListingOut], tags=["Listings"])
async def get_listings(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_score: Optional[float] = Query(None, ge=0.0, le=10.0),
    chip: Optional[str] = Query(None, max_length=64, description="Filter by chip e.g. 'M1 Max'"),
    min_ram: Optional[int] = Query(None, description="Minimum RAM in GB"),
    include_rejected: bool = Query(False)
):
    """
    List all stored listings with optional filters.
    """
    db = get_db()
    query = {}

    if not include_rejected:
        query["is_rejected"] = False
    if min_score is not None:
        query["deal_score"] = {"$gte": min_score}
    if chip:
        query["chip"] = {"$regex": re.escape(chip), "$options": "i"}
    if min_ram:
        query["ram_gb"] = {"$gte": min_ram}

    cursor = db.listings.find(query).sort("deal_score", -1).skip(offset).limit(limit)
    listings = await cursor.to_list(length=limit)
    
    # Map _id to id for the response
    for l in listings:
        l["id"] = str(l["_id"])
    return listings


@router.get("/listings/{listing_id}", response_model=ListingOut, tags=["Listings"])
async def get_listing(listing_id: str):
    """
    Retrieve a single listing by ID.
    """
    if not _LISTING_ID_RE.fullmatch(listing_id):
        raise HTTPException(status_code=400, detail="Invalid listing id format")

    db = get_db()
    listing = await db.listings.find_one({"_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    listing["id"] = str(listing["_id"])
    return listing


@router.get("/top-deals", response_model=list[ListingOut], tags=["Listings"])
async def get_top_deals(limit: int = Query(10, ge=1, le=50)):
    """
    Return the top-N highest-scored, non-rejected listings.
    """
    db = get_db()
    query = {
        "is_rejected": False,
        "deal_score": {"$ne": None}
    }
    
    cursor = db.listings.find(query).sort("deal_score", -1).limit(limit)
    listings = await cursor.to_list(length=limit)
    
    for l in listings:
        l["id"] = str(l["_id"])
    return listings


@router.get("/stats", response_model=StatsOut, tags=["Stats"])
async def get_stats():
    """
    Pipeline statistics overview.
    """
    db = get_db()
    
    total = await db.listings.count_documents({})
    notified = await db.listings.count_documents({"is_notified": True})
    rejected = await db.listings.count_documents({"is_rejected": True})
    
    # Aggregation for averages and max
    pipeline = [
        {"$match": {"is_rejected": False}},
        {"$group": {
            "_id": None,
            "avg_score": {"$avg": "$deal_score"},
            "avg_price": {"$avg": "$price"},
            "max_score": {"$max": "$deal_score"}
        }}
    ]
    
    agg_result = await db.listings.aggregate(pipeline).to_list(length=1)
    
    if agg_result:
        stats = agg_result[0]
        avg_score = stats.get("avg_score")
        avg_price = stats.get("avg_price")
        top_score = stats.get("max_score")
    else:
        avg_score = avg_price = top_score = None

    return StatsOut(
        total_listings=total,
        total_notified=notified,
        total_rejected=rejected,
        avg_deal_score=round(avg_score, 2) if avg_score else None,
        avg_price=round(avg_price, 2) if avg_price else None,
        top_score=round(top_score, 2) if top_score else None,
    )


@router.post("/scrape/run", response_model=RunResponse, tags=["Pipeline"])
async def trigger_scrape(
    request: Request,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key)
):
    """
    Manually trigger a pipeline run in the background.
    Protected by API key to prevent unauthorized scraping.
    """
    settings = get_settings()
    now = time.time()
    client_id = request.client.host if request.client else "unknown"
    bucket = _scrape_rate_limit_state[client_id]

    while bucket and now - bucket[0] > settings.scrape_rate_limit_window_seconds:
        bucket.popleft()

    if len(bucket) >= settings.scrape_rate_limit_max_requests:
        raise HTTPException(status_code=429, detail="Too many scrape requests. Please retry later.")

    bucket.append(now)

    from app.services.pipeline import run_pipeline
    background_tasks.add_task(run_pipeline)

    return RunResponse(
        status="started",
        message="Pipeline run started in background. Check logs for progress.",
    )
