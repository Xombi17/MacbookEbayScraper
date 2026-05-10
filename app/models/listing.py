from __future__ import annotations


from sqlalchemy import (
    String, Float, Integer, Boolean, Text, DateTime, func
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database.database import Base


class Listing(Base):
    """
    Represents a single eBay MacBook Pro listing extracted and scored by the pipeline.
    """
    __tablename__ = "listings"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    listing_url: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # ── Core Listing Data ─────────────────────────────────────────────────────
    title: Mapped[str | None] = mapped_column(String)
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10), default="USD")
    shipping_cost: Mapped[float | None] = mapped_column(Float)
    condition: Mapped[str | None] = mapped_column(String(100))
    return_policy: Mapped[str | None] = mapped_column(String(200))
    posted_date: Mapped[str | None] = mapped_column(String)

    # ── Hardware Specs (parsed) ───────────────────────────────────────────────
    chip: Mapped[str | None] = mapped_column(String(50))     # e.g. "M1 Max"
    ram_gb: Mapped[int | None] = mapped_column(Integer)       # e.g. 64
    storage_gb: Mapped[int | None] = mapped_column(Integer)   # e.g. 1024
    battery_health: Mapped[int | None] = mapped_column(Integer)  # e.g. 91 (%)

    # ── Seller Info ───────────────────────────────────────────────────────────
    seller_name: Mapped[str | None] = mapped_column(String(200))
    seller_rating: Mapped[float | None] = mapped_column(Float)  # 0.0–100.0

    # ── Media & Description ───────────────────────────────────────────────────
    image_url: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    raw_markdown: Mapped[str | None] = mapped_column(Text)   # Firecrawl output

    # ── AI Analysis ───────────────────────────────────────────────────────────
    scam_probability: Mapped[float | None] = mapped_column(Float)        # 0.0–1.0
    workstation_suitability: Mapped[float | None] = mapped_column(Float) # 0.0–10.0
    ai_llm_suitability: Mapped[float | None] = mapped_column(Float)      # 0.0–10.0
    pricing_quality: Mapped[str | None] = mapped_column(String(50))      # below/at/above market
    seller_trustworthiness: Mapped[str | None] = mapped_column(String(50))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(300))

    # ── Deal Score ────────────────────────────────────────────────────────────
    deal_score: Mapped[float | None] = mapped_column(Float)   # 0.0–10.0

    # ── Pipeline Tracking ─────────────────────────────────────────────────────
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Listing id={self.id!r} "
            f"title={self.title!r} "
            f"score={self.deal_score}>"
        )
