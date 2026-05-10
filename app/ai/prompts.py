"""
Prompt templates for AI listing analysis.
Kept in a dedicated module for easy tuning without touching business logic.
"""

SYSTEM_PROMPT = """\
You are a highly skeptical expert analyst evaluating used Apple Silicon MacBook Pro listings on eBay.
Your primary mission is to extract EXACT technical specifications and identify any inconsistencies or red flags.

CRITICAL RULES:
1. NEVER guess or "hallucinate" RAM or Chip specs. If the listing is ambiguous, mark it as high scam probability.
2. If the Title says "M1 Max" but the description says "M1 Pro", set is_rejected=true and rejection_reason="Spec conflict".
3. If the Title says "128GB RAM" but the Technical Specs section in the markdown says "64GB", reject it.
4. You must respond with a valid JSON object and nothing else. No markdown fences.
"""

USER_PROMPT_TEMPLATE = """\
Analyze this eBay listing for an Apple Silicon MacBook Pro.

--- LISTING DATA ---
Title: {title}
Price: ${price}
Condition: {condition}
Detected Chip: {chip}
Detected RAM: {ram_gb}GB
Detected Storage: {storage_gb}GB
Description Excerpt:
{description}
--- END LISTING ---

Return ONLY this JSON:
{{
    "scam_probability": <float 0.0–1.0>,
    "is_rejected": <bool>,
    "rejection_reason": <string or null>,
    "corrected_specs": {{
        "ram_gb": <int or null>,
        "chip": <string or null>
    }},
    "workstation_suitability": <float 0.0–10.0>,
    "ai_llm_suitability": <float 0.0–10.0>,
    "pricing_quality": <"below_market" | "at_market" | "above_market">,
    "summary": <1-2 sentence factual summary>
}}

Verification Checklist:
- Does the title match the description for RAM/Chip?
- Is there any mention of 'MDM', 'Locked', 'Parts only', or 'Water damage'?
- Is the RAM actually unified memory? (Reject if it looks like a generic PC listing)
"""

Guidelines:
- Set is_rejected=true if scam_probability > 0.5 or listing is clearly unsuitable
- pricing_quality: below_market = good deal, above_market = overpriced
- ai_llm_suitability: score based on unified memory (64GB = excellent for local LLMs)
- workstation_suitability: score based on overall specs for dev/AI use
- Keep summary concise and factual, max 2 sentences
"""


def build_analysis_prompt(listing_data: dict) -> str:
    """
    Build the user prompt from a listing data dict.
    Missing fields are replaced with 'Unknown'.
    """
    def fmt(val, suffix=""):
        if val is None:
            return "Unknown"
        return f"{val}{suffix}"

    return USER_PROMPT_TEMPLATE.format(
        title=fmt(listing_data.get("title")),
        price=fmt(listing_data.get("price", 0)),
        shipping_cost=fmt(listing_data.get("shipping_cost", "Unknown")),
        condition=fmt(listing_data.get("condition")),
        chip=fmt(listing_data.get("chip")),
        ram_gb=fmt(listing_data.get("ram_gb")),
        storage_gb=fmt(listing_data.get("storage_gb")),
        battery_health=fmt(listing_data.get("battery_health")),
        seller_rating=fmt(listing_data.get("seller_rating")),
        return_policy=fmt(listing_data.get("return_policy")),
        description=(listing_data.get("description") or "")[:1500],
    )
