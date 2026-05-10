"""
Listing parser — converts raw Firecrawl markdown into a structured ListingData model.

Uses regex + heuristics to extract:
- Price and shipping
- Chip model (M1/M2/M3/M4 Max/Pro/Base)
- RAM and storage
- Battery health
- Seller name and rating
- Condition and return policy
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class ListingData:
    """Structured representation of a parsed eBay listing."""
    listing_id: str
    listing_url: str
    raw_markdown: str

    title: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    shipping_cost: Optional[float] = None
    condition: Optional[str] = None
    return_policy: Optional[str] = None
    posted_date: Optional[str] = None

    # Hardware specs
    chip: Optional[str] = None        # e.g. "M1 Max"
    ram_gb: Optional[int] = None
    storage_gb: Optional[int] = None
    battery_health: Optional[int] = None

    # Seller
    seller_name: Optional[str] = None
    seller_rating: Optional[float] = None  # 0.0–100.0

    # Media
    image_url: Optional[str] = None
    description: Optional[str] = None

    images: list[str] = field(default_factory=list)


# ── Regex Patterns ────────────────────────────────────────────────────────────

# Price: "$1,349.00" or "US $1,349.00"
_PRICE_RE = re.compile(r"(?:US\s*)?\$\s*([\d,]+(?:\.\d{2})?)", re.IGNORECASE)

# Shipping: "Free shipping" or "+$12.45 shipping"
_SHIPPING_FREE_RE = re.compile(r"free\s+(?:standard\s+)?shipping", re.IGNORECASE)
_SHIPPING_COST_RE = re.compile(r"\+\$\s*([\d,]+(?:\.\d{2})?)\s+shipping", re.IGNORECASE)

# Chip model: M1/M2/M3/M4 Pro/Max/Base (optional "Apple" prefix)
_CHIP_RE = re.compile(
    r"\b(M[1-5])\s*(Max|Pro|Ultra|Base)?\b",
    re.IGNORECASE
)

# RAM: "64GB" "32 GB" "16gb" — must be near "RAM" / "memory" or standalone
_RAM_RE = re.compile(
    r"\b(8|16|24|32|36|48|64|96|128)\s*GB\b(?!\s*SSD|\s*storage)",
    re.IGNORECASE
)

# Storage: "1TB", "512GB SSD", "2TB SSD"
_STORAGE_TB_RE = re.compile(r"\b([1-9])\s*TB\b", re.IGNORECASE)
_STORAGE_GB_SSD_RE = re.compile(r"\b(256|512|1024|2048)\s*GB\s*(?:SSD|storage)?\b", re.IGNORECASE)

# Battery health: "Battery Health: 91%" or "91% battery"
_BATTERY_RE = re.compile(r"battery[\s\w]*?(\d{2,3})\s*%|(\d{2,3})\s*%\s*battery", re.IGNORECASE)

# Seller feedback: "99.4% positive feedback"
_SELLER_RATING_RE = re.compile(r"([\d.]+)\s*%\s*positive", re.IGNORECASE)

# Seller name: "Seller: username" or "Visit store\nusername"
_SELLER_NAME_RE = re.compile(r"Seller:\s*\*?\*?([^\n\*]+)\*?\*?", re.IGNORECASE)

# Condition
_CONDITION_RE = re.compile(
    r"Condition:\s*([^\n]+)",
    re.IGNORECASE
)

# Returns
_RETURNS_RE = re.compile(
    r"Returns?:\s*([^\n]+)",
    re.IGNORECASE
)

# Image URLs
_IMAGE_RE = re.compile(r"https?://[^\s\"']+\.(?:jpg|jpeg|png|webp)[^\s\"']*", re.IGNORECASE)


# ── Parser ────────────────────────────────────────────────────────────────────

class ListingParser:
    """
    Parses Firecrawl markdown output into a structured ListingData object.
    """

    def parse(
        self,
        listing_id: str,
        listing_url: str,
        markdown: str,
        metadata: dict,
    ) -> ListingData:
        data = ListingData(
            listing_id=listing_id,
            listing_url=listing_url,
            raw_markdown=markdown,
        )

        # Title — prefer metadata page title, fall back to first H1
        data.title = (
            metadata.get("title")
            or self._extract_h1(markdown)
        )

        # Price — Priority: Look for 'Buy It Now' or the main price block
        # We want the primary listing price, not a bid or a similar item's price.
        price_match = re.search(r"(?:Buy It Now|Price|Current bid):?\s*(?:US\s*)?\$\s*([\d,]+(?:\.\d{2})?)", markdown, re.IGNORECASE)
        if price_match:
            try:
                data.price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass
        
        if not data.price:
            # Fallback to general price regex but only in the first 2500 chars to avoid 'Similar Items'
            prices = _PRICE_RE.findall(markdown[:2500])
            if prices:
                try:
                    data.price = float(prices[0].replace(",", ""))
                except ValueError:
                    pass

        # Shipping
        if _SHIPPING_FREE_RE.search(markdown):
            data.shipping_cost = 0.0
        else:
            ship_match = _SHIPPING_COST_RE.search(markdown)
            if ship_match:
                try:
                    data.shipping_cost = float(ship_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Chip
        chip_match = _CHIP_RE.search(markdown)
        if chip_match:
            chip_gen = chip_match.group(1).upper()  # M1, M2, etc.
            chip_tier = chip_match.group(2)
            if chip_tier:
                chip_tier = chip_tier.capitalize()  # Max, Pro, etc.
                data.chip = f"{chip_gen} {chip_tier}"
            else:
                data.chip = chip_gen

        # RAM — pick the largest plausible value found
        ram_matches = _RAM_RE.findall(markdown)
        if ram_matches:
            data.ram_gb = max(int(v) for v in ram_matches)

        # Storage
        tb_matches = _STORAGE_TB_RE.findall(markdown)
        if tb_matches:
            data.storage_gb = max(int(v) for v in tb_matches) * 1024
        else:
            gb_matches = _STORAGE_GB_SSD_RE.findall(markdown)
            if gb_matches:
                data.storage_gb = max(int(v) for v in gb_matches)

        # Battery health
        batt_match = _BATTERY_RE.search(markdown)
        if batt_match:
            val = batt_match.group(1) or batt_match.group(2)
            if val:
                try:
                    bh = int(val)
                    if 0 < bh <= 100:
                        data.battery_health = bh
                except ValueError:
                    pass

        # Seller rating — avoid sponsored items by looking for context
        # eBay usually puts seller info in a specific block
        seller_section_match = re.search(r"Seller information.*?(?:\n|$)", markdown, re.IGNORECASE)
        if seller_section_match:
            section_text = markdown[seller_section_match.start():seller_section_match.start()+500]
            rating_match = _SELLER_RATING_RE.search(section_text)
            if rating_match:
                try:
                    data.seller_rating = float(rating_match.group(1))
                except ValueError:
                    pass
        else:
            # Fallback but check for "positive feedback" near the top
            rating_match = _SELLER_RATING_RE.search(markdown[:2000])
            if rating_match:
                try:
                    data.seller_rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # Seller name
        name_match = _SELLER_NAME_RE.search(markdown)
        if name_match:
            data.seller_name = name_match.group(1).strip()

        # Condition
        cond_match = _CONDITION_RE.search(markdown)
        if cond_match:
            data.condition = cond_match.group(1).strip()

        # Returns
        ret_match = _RETURNS_RE.search(markdown)
        if ret_match:
            data.return_policy = ret_match.group(1).strip()

        # Images
        data.images = list(set(_IMAGE_RE.findall(markdown)))[:5]
        if data.images:
            data.image_url = data.images[0]

        # Description — use the raw markdown trimmed
        data.description = markdown[:3000].strip()

        return data

    def _extract_h1(self, markdown: str) -> str | None:
        for line in markdown.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return None


# Module-level singleton
_parser: ListingParser | None = None


def get_parser() -> ListingParser:
    global _parser
    if _parser is None:
        _parser = ListingParser()
    return _parser
