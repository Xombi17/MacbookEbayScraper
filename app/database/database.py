"""
MongoDB async connection management using Motor.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from rich.console import Console

console = Console()

# Global client and database instances
_client: AsyncIOMotorClient | None = None
_db = None


async def init_db() -> None:
    """Initialize the MongoDB connection."""
    global _client, _db

    settings = get_settings()
    uri = settings.mongodb_uri
    
    if not uri:
        # Fallback for local dev if URI isn't provided
        uri = "mongodb://localhost:27017"
    
    _client = AsyncIOMotorClient(uri)
    # Use the database name from the URI or default to 'macbook_deals'
    db_name = uri.split("/")[-1].split("?")[0] or "macbook_deals"
    _db = _client[db_name]

    # Test connection
    try:
        await _client.admin.command('ping')
        console.print(
            f"[bold green]✓[/bold green] MongoDB initialized "
            f"([cyan]{db_name}[/cyan])"
        )
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] MongoDB connection failed: {e}")
        raise e


def get_db():
    """Return the global database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db
