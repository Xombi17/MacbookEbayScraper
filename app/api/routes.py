"""
FastAPI routes — REST API for querying listings and triggering pipeline runs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database.database import get_session
from app.models.listing import Listing

router = APIRouter()


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
    return_policy: Optional[str]
    image_url: Optional[str]
    listing_url: str
    deal_score: Optional[float]
    ai_summary: Optional[str]
    scam_probability: Optional[float]
    is_rejected: bool
    rejection_reason: Optional[str]
    is_notified: bool
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


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
    chip: Optional[str] = Query(None, description="Filter by chip e.g. 'M1 Max'"),
    min_ram: Optional[int] = Query(None, description="Minimum RAM in GB"),
    include_rejected: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """
    List all stored listings with optional filters.
    """
    stmt = select(Listing).order_by(desc(Listing.deal_score))

    if not include_rejected:
        stmt = stmt.where(Listing.is_rejected == False)  # noqa: E712
    if min_score is not None:
        stmt = stmt.where(Listing.deal_score >= min_score)
    if chip:
        stmt = stmt.where(Listing.chip.ilike(f"%{chip}%"))
    if min_ram:
        stmt = stmt.where(Listing.ram_gb >= min_ram)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    listings = result.scalars().all()
    return [ListingOut.model_validate(l) for l in listings]


@router.get("/listings/{listing_id}", response_model=ListingOut, tags=["Listings"])
async def get_listing(
    listing_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve a single listing by ID.
    """
    result = await session.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingOut.model_validate(listing)


@router.get("/top-deals", response_model=list[ListingOut], tags=["Listings"])
async def get_top_deals(
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """
    Return the top-N highest-scored, non-rejected listings.
    """
    result = await session.execute(
        select(Listing)
        .where(Listing.is_rejected == False)  # noqa: E712
        .where(Listing.deal_score.isnot(None))
        .order_by(desc(Listing.deal_score))
        .limit(limit)
    )
    listings = result.scalars().all()
    return [ListingOut.model_validate(l) for l in listings]


@router.get("/stats", response_model=StatsOut, tags=["Stats"])
async def get_stats(session: AsyncSession = Depends(get_session)):
    """
    Pipeline statistics overview.
    """
    total_result = await session.execute(select(func.count(Listing.id)))
    total = total_result.scalar() or 0

    notified_result = await session.execute(
        select(func.count(Listing.id)).where(Listing.is_notified == True)  # noqa: E712
    )
    notified = notified_result.scalar() or 0

    rejected_result = await session.execute(
        select(func.count(Listing.id)).where(Listing.is_rejected == True)  # noqa: E712
    )
    rejected = rejected_result.scalar() or 0

    avg_score_result = await session.execute(
        select(func.avg(Listing.deal_score)).where(Listing.is_rejected == False)  # noqa: E712
    )
    avg_score = avg_score_result.scalar()

    avg_price_result = await session.execute(
        select(func.avg(Listing.price)).where(Listing.price.isnot(None))
    )
    avg_price = avg_price_result.scalar()

    top_score_result = await session.execute(
        select(func.max(Listing.deal_score))
    )
    top_score = top_score_result.scalar()

    return StatsOut(
        total_listings=total,
        total_notified=notified,
        total_rejected=rejected,
        avg_deal_score=round(avg_score, 2) if avg_score else None,
        avg_price=round(avg_price, 2) if avg_price else None,
        top_score=round(top_score, 2) if top_score else None,
    )


@router.post("/scrape/run", response_model=RunResponse, tags=["Pipeline"])
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Manually trigger a pipeline run in the background.
    Returns immediately; the run happens asynchronously.
    """
    from app.services.pipeline import run_pipeline
    background_tasks.add_task(run_pipeline)

    return RunResponse(
        status="started",
        message="Pipeline run started in background. Check logs for progress.",
    )
