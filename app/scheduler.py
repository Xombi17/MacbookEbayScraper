"""
APScheduler — runs the pipeline on a configurable interval.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from rich.console import Console
from app.config import get_settings

console = Console()

_scheduler: AsyncIOScheduler | None = None


async def _scheduled_run():
    """Wrapper that catches exceptions so scheduler keeps running."""
    from app.services.pipeline import run_pipeline
    try:
        await run_pipeline()
    except Exception as exc:
        console.print(f"[red]✗ Scheduled pipeline run failed: {exc}[/red]")


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    settings = get_settings()
    scheduler = get_scheduler()

    scheduler.add_job(
        _scheduled_run,
        trigger=IntervalTrigger(hours=settings.run_interval_hours),
        id="pipeline_run",
        name="MacBook Deal Pipeline",
        replace_existing=True,
        misfire_grace_time=300,  # 5 minute grace window
    )

    scheduler.start()
    console.print(
        f"[bold green]⏰ Scheduler started[/bold green] — "
        f"pipeline runs every [cyan]{settings.run_interval_hours}h[/cyan]"
    )


def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        console.print("[dim]Scheduler stopped.[/dim]")
