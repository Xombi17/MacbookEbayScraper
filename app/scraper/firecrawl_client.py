"""
Firecrawl client — extracts structured markdown from individual eBay listing pages.

Credit optimization:
- Only called for NEW listing IDs (deduplication is upstream in rss_monitor)
- Structured extraction mode extracts schema directly, saving post-processing
"""

import asyncio
from firecrawl import FirecrawlApp
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.console import Console
from app.config import get_settings

console = Console()


class FirecrawlClient:
    """Thin wrapper around the Firecrawl SDK with retry logic."""

    def __init__(self):
        settings = get_settings()
        self._app = FirecrawlApp(api_key=settings.firecrawl_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _scrape_sync(self, url: str) -> dict:
        """Synchronous Firecrawl scrape (SDK is sync; we run in executor)."""
        return self._app.scrape_url(
            url,
            params={
                "formats": ["markdown", "html"],
                "onlyMainContent": True,
            }
        )

    async def extract_listing(self, url: str) -> dict | None:
        """
        Asynchronously extract a listing page.
        Returns a dict with 'markdown' and 'metadata' keys, or None on failure.
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self._scrape_sync, url)

            markdown = result.get("markdown", "") or ""
            metadata = result.get("metadata", {}) or {}

            if not markdown:
                console.print(f"  [yellow]⚠ Empty markdown returned for {url}[/yellow]")
                return None

            console.print(
                f"  [green]✓[/green] Scraped {url[:60]}... "
                f"([dim]{len(markdown)} chars[/dim])"
            )
            return {
                "markdown": markdown,
                "metadata": metadata,
                "url": url,
            }

        except Exception as exc:
            settings = get_settings()
            if settings.debug:
                console.print(f"  [red]✗ Firecrawl error for {url}: {exc}[/red]")
            else:
                console.print("  [red]✗ Firecrawl extraction failed[/red]")
            return None


# Module-level singleton
_client: FirecrawlClient | None = None


def get_firecrawl_client() -> FirecrawlClient:
    global _client
    if _client is None:
        _client = FirecrawlClient()
    return _client
