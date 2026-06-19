"""
Entry point for Bounty Scope Monitor.

Usage:
  python main.py              # Start the scheduler (daemon mode)
  python main.py --test       # Send a Telegram test notification and exit
  python main.py --run-once   # Run one poll cycle and exit (useful for cron)
"""

import asyncio
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.config import config
from core.database import init_db
from core.notifier import send_startup_message, test_notification
from core.processor import run_poll_cycle

console = Console()


# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging() -> None:
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
        colorize=True,
    )
    logger.add(
        "logs/bounties_monitor_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )


# ── Banner ─────────────────────────────────────────────────────────────────────

def print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]🎯 Bounty Scope Monitor[/bold cyan]\n"
            "[dim]Watches arkadiyt/bounty-targets-data for scope changes[/dim]",
            border_style="cyan",
        )
    )
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("📡 Platforms", ", ".join(config.enabled_platforms))
    table.add_row("⏱  Interval", f"every {config.poll_interval_minutes} minutes")
    table.add_row("💾 Database", config.database_path)
    table.add_row(
        "🔑 GitHub token",
        "✅ set" if config.github_token else "❌ not set (60 req/hr limit)",
    )
    console.print(table)
    console.print()


# ── Scheduler job ─────────────────────────────────────────────────────────────

def scheduled_job() -> None:
    """Wrapped poll cycle for the scheduler."""
    try:
        summary = run_poll_cycle()
        for platform, stats in summary.items():
            logger.info(
                f"  {platform}: {stats['programs']} programs, "
                f"{stats['changes']} changes"
            )
    except Exception as e:
        logger.exception(f"Unhandled error in poll cycle: {e}")


# ── Signal handling ───────────────────────────────────────────────────────────

def handle_shutdown(signum, frame) -> None:
    logger.info("Shutdown signal received. Stopping scheduler...")
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()

    # Parse simple CLI args
    args = sys.argv[1:]

    # ── Test mode ────────────────────────────────────────────────────────────
    if "--test" in args:
        console.print("[yellow]Sending Telegram test notification...[/yellow]")
        try:
            config.validate()
        except ValueError as e:
            console.print(f"[red]Config error: {e}[/red]")
            sys.exit(1)
        ok = test_notification()
        if ok:
            console.print("[green]Test notification sent successfully![/green]")
        else:
            console.print("[red]Failed to send test notification. Check your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.[/red]")
            sys.exit(1)
        return

    # ── CLI Commands: Recent Discovered / Updated Programs ───────────────────
    if "--recent-new" in args:
        from core.database import get_new_programs
        init_db()
        programs = get_new_programs(limit=15)
        
        table = Table(title="[NEW] Recently Discovered Programs (DB Query)", border_style="cyan")
        table.add_column("Platform", style="bold magenta")
        table.add_column("Name", style="bold white")
        table.add_column("Bounty Range", style="bold green")
        table.add_column("First Seen", style="dim cyan")
        table.add_column("URL", style="underline blue")

        for p in programs:
            min_b = f"${p.bounty_min:,.0f}" if p.bounty_min else ""
            max_b = f"${p.bounty_max:,.0f}" if p.bounty_max else ""
            bounty_str = f"{min_b} - {max_b} {p.bounty_currency}" if (min_b or max_b) else "VDP" if not p.offers_bounties else "Offers Bounty"
            
            table.add_row(
                p.platform.title(),
                p.name or p.handle,
                bounty_str,
                p.first_seen.strftime("%Y-%m-%d %H:%M"),
                p.url
            )
        console.print(table)
        return

    if "--recent-updates" in args:
        from core.database import get_recent_updates
        init_db()
        updates = get_recent_updates(limit=15)
        
        table = Table(title="[UPDATE] Recent Program Updates (DB Query)", border_style="green")
        table.add_column("Detected At", style="dim cyan")
        table.add_column("Platform", style="bold magenta")
        table.add_column("Program", style="bold white")
        table.add_column("Change Type", style="bold yellow")
        table.add_column("Detail", style="white")

        for u in updates:
            table.add_row(
                u.detected_at.strftime("%Y-%m-%d %H:%M"),
                u.platform.title(),
                u.program_name or u.program_handle,
                u.change_type.upper().replace("_", " "),
                u.detail or ""
            )
        console.print(table)
        return

    # ── Run-once mode ────────────────────────────────────────────────────────
    if "--run-once" in args:
        console.print("[yellow]Running one poll cycle (notifications skipped)...[/yellow]")
        try:
            config.validate()
        except ValueError as e:
            console.print(f"[red]Config error: {e}[/red]")
            sys.exit(1)
        init_db()
        run_poll_cycle(skip_notifications=True)
        return

    # ── Daemon mode ──────────────────────────────────────────────────────────
    print_banner()

    try:
        config.validate()
    except ValueError as e:
        console.print(f"[bold red]❌ Configuration Error:[/bold red] {e}")
        sys.exit(1)

    # Initialize database
    init_db()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Import bot listener
    from core.bot_listener import run_bot_listener

    # Create event loop for bot listener and startup notifications
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(send_startup_message())
    loop.run_until_complete(run_bot_listener())

    # Run first cycle immediately on startup
    logger.info("Running initial poll cycle on startup...")
    scheduled_job()

    # Start scheduler
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_job,
        trigger=IntervalTrigger(minutes=config.poll_interval_minutes),
        id="poll_cycle",
        name="Poll bounty-targets-data",
        max_instances=1,          # Prevent overlapping runs
        coalesce=True,
    )

    next_run = datetime.utcnow()
    logger.info(
        f"Scheduler started. Next poll in {config.poll_interval_minutes} minutes. "
        f"Press Ctrl+C to stop."
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bounty Monitor stopped.")


if __name__ == "__main__":
    main()
