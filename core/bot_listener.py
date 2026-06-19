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
    """List recently added programs to database."""
    programs = get_new_programs(limit=10)
    if not programs:
        await update.message.reply_text("❌ No programs found in database yet.")
        return

    lines = [
        "🆕 *Recently Discovered Programs*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for p in programs:
        platform = p.platform.title()
        name = p.name or p.handle
        min_b = f"${p.bounty_min:,.0f}" if p.bounty_min else ""
        max_b = f"${p.bounty_max:,.0f}" if p.bounty_max else ""
        
        bounty_str = f"\\({min_b} ➜ {max_b} {p.bounty_currency}\\)" if (min_b or max_b) else "\\(VDP\\)" if not p.offers_bounties else "\\(Offers Bounty\\)"
        
        lines.append(f"• *{_escape(platform)}* — [{_escape(name)}]({_escape(p.url)}) {bounty_str}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, disable_web_page_preview=True)


async def recent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent updates from database change log."""
    updates = get_recent_updates(limit=10)
    if not updates:
        await update.message.reply_text("❌ No recent updates logged in database yet.")
        return

    lines = [
        "🔄 *Recent Scope & Bounty Updates*",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for u in updates:
        ts = u.detected_at.strftime("%m\\-%d %H:%M")
        platform = u.platform.title()
        prog = u.program_name or u.program_handle
        chg_type = u.change_type.upper().replace("_", " ")
        detail = u.detail or ""
        
        lines.append(
            f"📅 `{ts}` *{_escape(platform)}* — [{_escape(prog)}]({_escape(u.program_url)})\n"
            f"  ▸ `{_escape(chg_type)}`: _{_escape(detail)}_\n"
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
