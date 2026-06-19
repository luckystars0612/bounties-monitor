"""
Bot commands listener. 
Listens for interactive commands in Telegram (e.g. /new, /recent) using python-telegram-bot's Application class.
Runs as a background service alongside the main poll scheduler.
"""

import asyncio
from loguru import logger
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from core.config import config
from core.database import get_new_programs, get_recent_updates
from core.notifier import _escape


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send basic welcome details and help."""
    help_text = (
        "🤖 *Bounty Scope Monitor Commands:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ `/new` — Show recently discovered bug bounty programs\n"
        "🔄 `/recent` — Show the 10 most recent scope/bounty changes\n"
        "ℹ️ `/status` — View current monitor settings"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)


async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List 3 recently added programs per platform from the database."""
    # We will query more programs from DB and filter/group them locally to get 3 per platform
    from core.database import get_new_programs
    programs = get_new_programs(limit=100)
    
    if not programs:
        await update.message.reply_text("❌ No programs found in database yet.")
        return

    # Group by platform and take top 3
    grouped = {}
    for p in programs:
        grouped.setdefault(p.platform, []).append(p)

    lines = [
        "🆕 *Recently Discovered Programs (3 per platform)*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    for platform, p_list in grouped.items():
        platform_title = platform.title()
        lines.append(f"\n*📡 {platform_title}*")
        for p in p_list[:3]:
            name = p.name or p.handle
            min_b = f"${p.bounty_min:,.0f}" if p.bounty_min else ""
            max_b = f"${p.bounty_max:,.0f}" if p.bounty_max else ""
            bounty_str = f"\\({min_b} ➜ {max_b} {p.bounty_currency}\\)" if (min_b or max_b) else "\\(VDP\\)" if not p.offers_bounties else "\\(Offers Bounty\\)"
            lines.append(f"  • [{_escape(name)}]({_escape(p.url)}) {bounty_str}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)


async def recent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List 3 recent scope target changes per platform (excluding simple bounty price changes)."""
    # Query updates from DB and filter out bounty increases/decreases (ChangeType.BOUNTY_INCREASE / BOUNTY_DECREASE)
    # and only show scope additions/removals
    from core.database import get_recent_updates
    from core.models import ChangeType
    
    updates = get_recent_updates(limit=200)
    # Filter to only keep new_scope and removed_scope
    scope_updates = [
        u for u in updates 
        if u.change_type in (ChangeType.NEW_SCOPE.value, ChangeType.REMOVED_SCOPE.value, ChangeType.NEW_PROGRAM.value)
    ]

    if not scope_updates:
        await update.message.reply_text("❌ No recent scope changes logged in database yet.")
        return

    # Group by platform and take top 3
    grouped = {}
    for u in scope_updates:
        grouped.setdefault(u.platform, []).append(u)

    lines = [
        "🔄 *Recent Scope Updates (3 per platform)*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    for platform, u_list in grouped.items():
        platform_title = platform.title()
        lines.append(f"\n*📡 {platform_title}*")
        for u in u_list[:3]:
            # Convert UTC to UTC+7 (Asia/Ho_Chi_Minh) and format as '2026-6-19 11:43 +07'
            from datetime import timedelta
            local_time = u.detected_at + timedelta(hours=7)
            # %#m and %#d are Windows-specific single-digit formatting options,
            # but we also support cross-platform replacement for compatibility.
            ts = local_time.strftime("%Y\\-%#m\\-%#d %H:%M +07")
            
            prog = u.program_name or u.program_handle
            chg_type = u.change_type.upper().replace("_", " ")
            detail = u.detail or ""
            
            lines.append(
                f"  • [{_escape(prog)}]({_escape(u.program_url)}) \\- `{_escape(chg_type)}`\n"
                f"    _{_escape(detail)}_ \\(`{ts}`\\)"
            )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return status information."""
    platforms = ", ".join(config.enabled_platforms)
    status_msg = (
        "📈 *Bounties Monitor Status*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *Platforms:* {_escape(platforms)}\n"
        f"⏱ *Poll Interval:* every {config.poll_interval_minutes} minutes\n"
        f"💰 *Bounties Only:* `{config.bounties_only}`\n"
        f"📦 *Storage:* `{_escape(config.database_path)}`"
    )
    await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN_V2)


async def run_bot_listener() -> None:
    """Initialize and run the Telegram bot polling engine."""
    logger.info("Initializing Telegram bot command listener...")
    application = ApplicationBuilder().token(config.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", start_cmd))
    application.add_handler(CommandHandler("new", new_cmd))
    application.add_handler(CommandHandler("recent", recent_cmd))
    application.add_handler(CommandHandler("status", status_cmd))

    # Initialize and start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Telegram Bot listener started successfully.")
