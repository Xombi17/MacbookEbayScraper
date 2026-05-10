"""
Deal Scoring Engine — ranks listings using weighted heuristics.

Scoring philosophy (from AGENTS.md):
1. RAM — most important (AI workloads need unified memory)
2. Max-tier chip — second most important
3. Seller trust — returns accepted, high feedback %
4. Battery health — longevity indicator
5. Condition — cosmetic / functional quality
6. Price penalty — penalize overpriced listings
7. Pricing quality bonus — AI-assessed market positioning

Scores are normalized to 0.0–10.0
"""

from dataclasses import dataclass
from typing import Optional

from app.scraper.listing_parser import ListingData
from app.ai.ai_filter import AIAnalysis


# ── Score Component Breakdown ─────────────────────────────────────────────────

@dataclass
class ScoreBreakdown:
    ram_score: float = 0.0
    chip_score: float = 0.0
    seller_score: float = 0.0
    battery_score: float = 0.0
    condition_score: float = 0.0
    price_penalty: float = 0.0
    pricing_quality_bonus: float = 0.0

    total_raw: float = 0.0
    normalized: float = 0.0  # final 0.0–10.0

    def __str__(self) -> str:
        return (
            f"RAM={self.ram_score:.1f} | Chip={self.chip_score:.1f} | "
            f"Seller={self.seller_score:.1f} | Batt={self.battery_score:.1f} | "
            f"Cond={self.condition_score:.1f} | "
            f"PricePenalty=-{self.price_penalty:.1f} | "
            f"PricingBonus=+{self.pricing_quality_bonus:.1f} | "
            f"→ {self.normalized:.2f}/10"
        )


# ── Scoring Constants ─────────────────────────────────────────────────────────

# Maximum possible raw points (before penalties)
MAX_POSSIBLE_RAW = 40 + 35 + 25 + 15 + 15 + 5  # 135


def _ram_score(ram_gb: Optional[int]) -> float:
    if ram_gb is None:
        return 0.0
    if ram_gb >= 64:
        return 40.0
    if ram_gb >= 32:
        return 25.0
    if ram_gb >= 16:
        return 5.0
    return 0.0


def _chip_score(chip: Optional[str]) -> float:
    if not chip:
        return 0.0
    chip_upper = chip.upper()
    if "MAX" in chip_upper or "ULTRA" in chip_upper:
        return 35.0
    if "PRO" in chip_upper:
        return 20.0
    return 5.0  # Base chip


def _seller_score(
    seller_rating: Optional[float],
    return_policy: Optional[str],
) -> float:
    score = 0.0

    if seller_rating is not None:
        if seller_rating >= 99.0:
            score += 15.0
        elif seller_rating >= 97.0:
            score += 10.0
        elif seller_rating >= 95.0:
            score += 5.0

    if return_policy:
        rp_lower = return_policy.lower()
        if "accept" in rp_lower or "30" in rp_lower or "60" in rp_lower:
            score += 10.0
        elif "no return" not in rp_lower:
            score += 3.0

    return min(score, 25.0)


def _battery_score(battery_health: Optional[int]) -> float:
    if battery_health is None:
        return 5.0  # neutral if unknown
    if battery_health >= 90:
        return 15.0
    if battery_health >= 80:
        return 10.0
    if battery_health >= 70:
        return 5.0
    return 0.0


def _condition_score(condition: Optional[str]) -> float:
    if not condition:
        return 5.0
    c = condition.lower()
    if "new" in c or "mint" in c:
        return 15.0
    if "excellent" in c or "like new" in c:
        return 12.0
    if "very good" in c or "great" in c:
        return 10.0
    if "good" in c:
        return 7.0
    if "acceptable" in c or "fair" in c:
        return 3.0
    return 5.0


def _price_penalty(
    price: Optional[float],
    max_price_usd: float = 1500.0,
) -> float:
    """
    Penalizes listings that are expensive relative to the max acceptable price.
    """
    if price is None:
        return 5.0

    ratio = price / max_price_usd
    if ratio <= 0.6:
        return 0.0
    if ratio <= 0.8:
        return 3.0
    if ratio <= 1.0:
        return 10.0
    return 25.0


def _pricing_quality_bonus(pricing_quality: Optional[str]) -> float:
    if pricing_quality == "below_market":
        return 5.0
    if pricing_quality == "above_market":
        return -5.0
    return 0.0


# ── Main Scorer ────────────────────────────────────────────────────────────────

class DealRanker:
    def __init__(self, max_price_usd: float = 1500.0):
        self.max_price_usd = max_price_usd

    def score(
        self,
        listing: ListingData,
        analysis: Optional[AIAnalysis] = None,
    ) -> ScoreBreakdown:
        """
        Compute deal score for a listing.
        Returns a ScoreBreakdown with component values and final 0–10 score.
        """
        breakdown = ScoreBreakdown()

        breakdown.ram_score = _ram_score(listing.ram_gb)
        breakdown.chip_score = _chip_score(listing.chip)
        breakdown.seller_score = _seller_score(listing.seller_rating, listing.return_policy)
        breakdown.battery_score = _battery_score(listing.battery_health)
        breakdown.condition_score = _condition_score(listing.condition)
        breakdown.price_penalty = _price_penalty(listing.price, self.max_price_usd)

        if analysis:
            breakdown.pricing_quality_bonus = _pricing_quality_bonus(analysis.pricing_quality)

        breakdown.total_raw = (
            breakdown.ram_score
            + breakdown.chip_score
            + breakdown.seller_score
            + breakdown.battery_score
            + breakdown.condition_score
            + breakdown.pricing_quality_bonus
            - breakdown.price_penalty
        )

        # Normalize to 0–10
        breakdown.normalized = max(
            0.0,
            min(10.0, (breakdown.total_raw / MAX_POSSIBLE_RAW) * 10.0)
        )

        return breakdown


# Module-level singleton
_ranker: DealRanker | None = None


def get_ranker() -> DealRanker:
    global _ranker
    if _ranker is None:
        from app.config import get_settings
        settings = get_settings()
        _ranker = DealRanker(max_price_usd=settings.max_price_usd)
    return _ranker
