"""
Prompt templates for AI listing analysis.
Kept in a dedicated module for easy tuning without touching business logic.
"""

SYSTEM_PROMPT = """\
You are a highly skeptical expert analyst evaluating used Apple Silicon MacBook Pro listings on eBay.
Your primary mission is to extract EXACT technical specifications and identify any inconsistencies or red flags.

CURRENT CONTEXT (May 2026):
- M1, M2, M3, M4, and M5 chips are all VALID and released. 
- Do NOT flag M4 or M5 as "non-existent". 
- Accept RAM up to 128GB as valid for Max/Ultra models.

CRITICAL RULES:
1. NEVER guess or "hallucinate" RAM or Chip specs. If the listing is ambiguous, mark it as high scam probability.
2. If the Title says "M1 Max" but the description says "M1 Pro", set is_rejected=true and rejection_reason="Spec conflict".
3. If the Title says "128GB RAM" but the Technical Specs section in the markdown says "64GB", reject it.
4. SELLER REPUTATION: If a seller has >98% positive feedback, they are likely trustworthy. Be less skeptical of low prices from these sellers unless there are clear hardware red flags (like MDM or M5 chip).
5. You must respond with a valid JSON object and nothing else. No markdown fences.
"""

USER_PROMPT_TEMPLATE = """\
Analyze this eBay listing for an Apple Silicon MacBook Pro.

--- LISTING DATA ---
Title: {title}
Price: ${price}
Condition: {condition}
Seller Rating: {seller_rating}%
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


PRE_FILTER_PROMPT_TEMPLATE = """\
Identify the top {limit} best potential deals from this list of MacBook Pro eBay search results.
Focus on Apple Silicon (M1/M2/M3/M4/M5) Max models with high RAM (32GB, 64GB, 96GB, 128GB).
Reject anything that is obviously:
- "Broken", "Cracked", "Parts only", "MDM", "Locked", "AS IS"
- Overpriced (e.g. M1 for $3000)
- Not an Apple Silicon MacBook

--- LISTINGS ---
{listings_json}
--- END ---

Return ONLY a JSON object with a list of indices that are "Worth investigating":
{{
    "worth_investigating": [index1, index2, ...]
}}
"""


def build_pre_filter_prompt(listings: list[dict], limit: int) -> str:
    """Prepare a compact list for the AI to judge."""
    import json
    compact_list = []
    for i, l in enumerate(listings):
        compact_list.append({
            "index": i,
            "title": l.get("title"),
            "price": l.get("price_str")
        })
        
    return PRE_FILTER_PROMPT_TEMPLATE.format(
        limit=limit,
        listings_json=json.dumps(compact_list, indent=2)
    )
