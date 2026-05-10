"""
MacBook Deal Intelligence System — FastAPI application entrypoint.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

from app.config import get_settings
from app.database.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.api.routes import router

console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    console.rule("[bold cyan]MacBook Deal Intelligence[/bold cyan]")
    console.print(f"[dim]Version {settings.app_version}[/dim]")

    # Ensure data directory exists (for SQLite)
    if settings.database_type == "sqlite":
        os.makedirs(os.path.dirname(settings.sqlite_path), exist_ok=True)

    # Initialize database and create tables
    await init_db()

    # Start background scheduler
    start_scheduler()

    console.rule("[bold green]✓ Application Ready[/bold green]")

    yield  # ← Application runs here

    # Shutdown
    stop_scheduler()
    console.print("[dim]Shutting down...[/dim]")


# ── FastAPI App ────────────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered eBay MacBook Pro deal monitoring system. "
        "Tracks, filters, scores, and alerts on high-value Apple Silicon listings."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for dev (restrict in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
