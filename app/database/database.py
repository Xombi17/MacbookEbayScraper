"""
SQLAlchemy async database engine and session management.
Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_TYPE env var.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings
from rich.console import Console

console = Console()


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Module-level engine/session — initialized on first call to init_db()
_engine = None
_async_session_factory = None


async def init_db() -> None:
    """Initialize the database engine and create all tables."""
    global _engine, _async_session_factory

    settings = get_settings()
    db_url = settings.get_database_url()

    connect_args = {}
    if settings.database_type == "sqlite":
        connect_args["check_same_thread"] = False

    _engine = create_async_engine(
        db_url,
        echo=settings.debug,
        connect_args=connect_args,
    )

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import models so metadata is populated before create_all
    import app.models.listing  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    console.print(
        f"[bold green]✓[/bold green] Database initialized "
        f"([cyan]{settings.database_type}[/cyan])"
    )


async def get_session() -> AsyncSession:
    """
    Dependency-injectable async session.
    Usage in FastAPI: `session: AsyncSession = Depends(get_session)`
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _async_session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker:
    """Return the session factory for use outside of FastAPI DI (e.g., pipeline)."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory
