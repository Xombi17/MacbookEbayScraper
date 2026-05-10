"""
Telegram notification system — sends formatted deal alerts.

Alert criteria (from config):
- deal_score >= DEAL_SCORE_THRESHOLD
- listing is not already notified
- scam_probability is low
"""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from rich.console import Console
from app.config import get_settings

console = Console()


def _format_alert(listing: dict) -> str:
    """Build the formatted Telegram alert message."""

    # Score bar (visual)
    score = listing.get("deal_score") or 0.0
    filled = int(score)
    bar = "█" * filled + "░" * (10 - filled)

    # Chip + RAM line
    specs = []
    if listing.get("chip"):
        specs.append(listing["chip"])
    if listing.get("ram_gb"):
        specs.append(f"{listing['ram_gb']}GB RAM")
    if listing.get("storage_gb"):
        tb = listing["storage_gb"] / 1024
        specs.append(f"{tb:.0f}TB SSD" if tb >= 1 else f"{listing['storage_gb']}GB SSD")
    specs_str = " · ".join(specs) if specs else "Specs unknown"

    # Price line
    price = listing.get("price")
    shipping = listing.get("shipping_cost")
    
    price_str = f"${price:,.0f}" if price else "Price unknown"
    if shipping and shipping > 0:
        price_str += f" + ${shipping:.0f} shipping"
    elif shipping == 0:
        price_str += " (free shipping)"

    # Seller line
    seller_parts = []
    if listing.get("seller_name"):
        seller_parts.append(listing["seller_name"])
    if listing.get("seller_rating"):
        seller_parts.append(f"{listing['seller_rating']:.1f}% feedback")
    seller_str = " · ".join(seller_parts) if seller_parts else "Seller unknown"

    # Battery
    batt_str = f"{listing['battery_health']}%" if listing.get("battery_health") else "Not reported"

    # Condition
    cond_str = listing.get("condition") or "Unknown"

    # Returns
    ret_str = listing.get("return_policy") or "Unknown"

    # AI summary
    summary_str = listing.get("ai_summary") or "No AI summary available."

    title = listing.get("title") or 'MacBook Pro'
    
    return (
        f"🔥 *High-Value MacBook Deal*\n\n"
        f"*{title}*\n"
        f"`{specs_str}`\n\n"
        f"💰 *Price:* {price_str}\n"
        f"🔋 *Battery:* {batt_str}\n"
        f"📦 *Condition:* {cond_str}\n"
        f"🔄 *Returns:* {ret_str}\n"
        f"🏪 *Seller:* {seller_str}\n\n"
        f"📊 *Deal Score:* {score:.1f}/10\n"
        f"`[{bar}]`\n\n"
        f"🤖 *AI Summary:*\n_{summary_str}_"
    )


async def send_deal_alert(listing: dict) -> bool:
    """
    Send a Telegram alert for a high-value listing.
    Returns True on success, False on failure.
    """
    settings = get_settings()

    if not settings.enable_telegram:
        console.print("  [dim]Telegram disabled — skipping notification[/dim]")
        return False

    try:
        bot = Bot(token=settings.telegram_bot_token)

        message = _format_alert(listing)

        # Inline button to open the listing
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text="🔗 Open Listing on eBay",
                url=listing.get("url") or listing.get("listing_url", "https://ebay.com"),
            )]
        ])

        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )
        
        title = listing.get("title") or 'Unknown'
        score = listing.get("deal_score") or 0.0
        
        console.print(
            f"  [bold green]📬 Telegram alert sent[/bold green]: "
            f"{title[:50]}... "
            f"(score={score:.1f})"
        )
        return True

    except Exception as exc:
        console.print(f"  [red]✗ Telegram error: {exc}[/red]")
        return False
