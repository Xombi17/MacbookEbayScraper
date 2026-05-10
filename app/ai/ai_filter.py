"""
AI Filter — OpenAI-powered scam detection and listing quality classification.

Two-stage filtering:
1. Fast keyword pre-filter (no API cost)
2. OpenAI structured analysis (only for listings passing stage 1)
"""

import json
import asyncio
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.console import Console

from app.config import get_settings, BAD_KEYWORDS
from app.ai.prompts import SYSTEM_PROMPT, build_analysis_prompt
from app.scraper.listing_parser import ListingData

console = Console()


# ── Result Schema ─────────────────────────────────────────────────────────────

@dataclass
class AIAnalysis:
    scam_probability: float = 0.0
    is_rejected: bool = False
    rejection_reason: Optional[str] = None
    workstation_suitability: float = 5.0
    ai_llm_suitability: float = 5.0
    pricing_quality: str = "at_market"
    seller_trustworthiness: str = "medium"
    summary: str = ""
    skipped_ai: bool = False  # True if pre-filter caught it or AI disabled


# ── Keyword Pre-filter ────────────────────────────────────────────────────────

def keyword_pre_filter(listing: ListingData) -> tuple[bool, Optional[str]]:
    """
    Check listing title + description for disqualifying keywords.

    Returns:
        (is_rejected: bool, reason: str | None)
    """
    text = " ".join([
        listing.title or "",
        listing.description or "",
    ]).lower()

    for kw in BAD_KEYWORDS:
        if kw.lower() in text:
            return True, f"Keyword match: '{kw}'"

    return False, None


# ── OpenAI Analysis ───────────────────────────────────────────────────────────

class AIFilter:
    def __init__(self):
        settings = get_settings()
        # GitHub Models is OpenAI-SDK-compatible — just point to their endpoint
        self._client = AsyncOpenAI(
            base_url=settings.github_models_endpoint,
            api_key=settings.github_token,
        )
        self._model = settings.github_chat_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def _call_openai(self, listing_dict: dict) -> dict:
        """Call OpenAI and parse the JSON response."""
        prompt = build_analysis_prompt(listing_dict)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    async def analyze(self, listing: ListingData) -> AIAnalysis:
        """
        Full analysis pipeline for a single listing.
        Pre-filters first; calls OpenAI only if listing passes.
        """
        settings = get_settings()

        # Stage 1: keyword pre-filter (free)
        rejected, reason = keyword_pre_filter(listing)
        if rejected:
            console.print(
                f"  [yellow]⚡ Pre-filter rejected[/yellow]: {reason} "
                f"| {listing.title[:50] if listing.title else 'Unknown'}..."
            )
            return AIAnalysis(
                is_rejected=True,
                rejection_reason=reason,
                scam_probability=0.9,
                skipped_ai=True,
                summary=f"Rejected by keyword filter: {reason}",
            )

        # Stage 2: OpenAI analysis (paid)
        if not settings.enable_ai_filter:
            return AIAnalysis(
                skipped_ai=True,
                summary="AI filtering disabled.",
            )

        try:
            result = await self._call_openai(listing.__dict__)
            
            # Apply corrections from AI if provided
            corrected = result.get("corrected_specs", {})
            if corrected.get("ram_gb"):
                listing.ram_gb = int(corrected["ram_gb"])
            if corrected.get("chip"):
                listing.chip = str(corrected["chip"])

            return AIAnalysis(
                scam_probability=float(result.get("scam_probability", 0.0)),
                is_rejected=bool(result.get("is_rejected", False)),
                rejection_reason=result.get("rejection_reason"),
                workstation_suitability=float(result.get("workstation_suitability", 5.0)),
                ai_llm_suitability=float(result.get("ai_llm_suitability", 5.0)),
                pricing_quality=result.get("pricing_quality", "at_market"),
                seller_trustworthiness="medium", # Simplified
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            console.print(f"  [red]✗ AI analysis failed: {exc}[/red]")
            # Fail open — don't reject listing on API error
            return AIAnalysis(
                skipped_ai=True,
                summary="AI analysis failed; manual review recommended.",
            )


# Module-level singleton
_filter: AIFilter | None = None


def get_ai_filter() -> AIFilter:
    global _filter
    if _filter is None:
        _filter = AIFilter()
    return _filter
