"""
Telegram notifier: formats and sends scope change alerts.
Uses python-telegram-bot with rate limiting and message splitting.
"""

import asyncio
from datetime import datetime
from typing import List

from loguru import logger
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from core.config import config
from core.models import ChangeType, ScopeChange

# Platform display config
PLATFORM_EMOJI = {
    "hackerone":  "🟠",
    "bugcrowd":   "🔵",
    "intigriti":  "🟣",
    "yeswehack":  "🟡",
}

PLATFORM_LABEL = {
    "hackerone":  "HackerOne",
    "bugcrowd":   "Bugcrowd",
    "intigriti":  "Intigriti",
    "yeswehack":  "YesWeHack",
}

CHANGE_EMOJI = {
    ChangeType.NEW_SCOPE:       "✅",
    ChangeType.REMOVED_SCOPE:   "❌",
    ChangeType.NEW_PROGRAM:     "🎉",
    ChangeType.BOUNTY_INCREASE: "💰",
    ChangeType.BOUNTY_DECREASE: "📉",
    ChangeType.PROGRAM_UPDATED: "🔄",
}

CHANGE_TITLE = {
    ChangeType.NEW_SCOPE:       "New Scope Added",
    ChangeType.REMOVED_SCOPE:   "Scope Removed",
    ChangeType.NEW_PROGRAM:     "New Program Discovered",
    ChangeType.BOUNTY_INCREASE: "Bounty Increased 💰",
    ChangeType.BOUNTY_DECREASE: "Bounty Decreased",
    ChangeType.PROGRAM_UPDATED: "Program Updated",
}

# Max scopes to show per notification (avoid huge messages)
MAX_SCOPES_IN_MSG = 15
# Telegram max message length
MAX_MSG_LEN = 4096


def _escape(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def _format_scope_list(scopes: list, header: str, emoji: str = "•") -> str:
    """Format a list of scope items into readable text."""
    if not scopes:
        return ""

    lines = [f"*{_escape(header)}*"]
    shown = scopes[:MAX_SCOPES_IN_MSG]

    for item in shown:
        asset = item.asset_identifier
        bounty_tag = " \\[💰\\]" if item.eligible_for_bounty else " \\[VDP\\]"
        severity = f" `{_escape(item.max_severity)}`" if item.max_severity and item.max_severity not in ("none", "null") else ""
        lines.append(f"  {emoji} `{_escape(asset)}`{bounty_tag}{severity}")

    if len(scopes) > MAX_SCOPES_IN_MSG:
        remaining = len(scopes) - MAX_SCOPES_IN_MSG
        lines.append(f"  _\\.\\.\\. and {remaining} more_")

    return "\n".join(lines)


def format_message(change: ScopeChange) -> str:
    """
    Build a Telegram MarkdownV2 message for a single ScopeChange.
    """
    platform_emoji = PLATFORM_EMOJI.get(change.platform, "🔔")
    platform_label = PLATFORM_LABEL.get(change.platform, change.platform.title())
    change_emoji   = CHANGE_EMOJI.get(change.change_type, "🔔")
    change_title   = CHANGE_TITLE.get(change.change_type, "Update")

    # Windows does not support %-m or %-d. Use %#m and %#d instead, or generic formatting.
    # To keep it cross-platform and safe, we can use string formatting or replace '-' with '#' on Windows
    # since we are running on Windows right now.
    ts = change.detected_at.strftime("%Y\\-%#m\\-%#d %H:%M UTC")

    lines = [
        f"{platform_emoji} *\\[{_escape(platform_label)}\\] {_escape(change_title)}*",
        f"📌 [{_escape(change.program_name)}]({_escape(change.program_url)})",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Scope additions
    if change.added_scopes:
        lines.append(
            _format_scope_list(change.added_scopes, "✅ New In-Scope Targets:", "▸")
        )

    # Scope removals
    if change.removed_scopes:
        lines.append(
            _format_scope_list(change.removed_scopes, "❌ Removed Scopes:", "▸")
        )

    # Bounty change
    if change.old_bounty and change.new_bounty:
        old = _escape(str(change.old_bounty))
        new = _escape(str(change.new_bounty))
        lines.append(f"💰 *Bounty:* {old} ➜ {new}")

    lines.append(f"\n⏰ _{ts}_")

    return "\n".join(lines)


def format_new_program_message(change: ScopeChange) -> str:
    """Special formatting for new program notifications."""
    platform_emoji = PLATFORM_EMOJI.get(change.platform, "🔔")
    platform_label = PLATFORM_LABEL.get(change.platform, change.platform.title())
    ts = change.detected_at.strftime("%Y\\-%#m\\-%#d %H:%M UTC")

    lines = [
        f"🎉 *New Bug Bounty Program\\!*",
        f"{platform_emoji} *{_escape(platform_label)}* \\— [{_escape(change.program_name)}]({_escape(change.program_url)})",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if change.added_scopes:
        lines.append(
            _format_scope_list(
                change.added_scopes,
                f"🎯 In-Scope Targets ({len(change.added_scopes)}):",
                "▸"
            )
        )
    else:
        lines.append("_No public scope listed yet_")

    lines.append(f"\n⏰ _{ts}_")
    return "\n".join(lines)


async def _send_async(message: str) -> bool:
    """Send a single Telegram message, truncating if needed."""
    bot = Bot(token=config.telegram_bot_token)
    # Truncate if too long
    if len(message) > MAX_MSG_LEN:
        message = message[: MAX_MSG_LEN - 20] + "\n_\\[truncated\\]_"
    try:
        await bot.send_message(
            chat_id=config.telegram_chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
        return True
    except TelegramError as e:
        logger.error(f"Telegram send failed: {e}")
        # Fallback: send as plain text
        try:
            plain = message.replace("\\", "").replace("*", "").replace("`", "")
            await bot.send_message(
                chat_id=config.telegram_chat_id,
                text=plain,
                disable_web_page_preview=True,
            )
            return True
        except TelegramError as e2:
            logger.error(f"Telegram fallback also failed: {e2}")
            return False


def send_change(change: ScopeChange) -> bool:
    """Format and send a scope change notification. Returns True on success."""
    if change.change_type == ChangeType.NEW_PROGRAM:
        message = format_new_program_message(change)
    else:
        message = format_message(change)

    return asyncio.run(_send_async(message))


def send_changes(changes: List[ScopeChange]) -> int:
    """
    Send notifications for a list of changes.
    Returns number of successfully sent messages.
    """
    sent = 0
    for change in changes:
        try:
            if send_change(change):
                sent += 1
        except Exception as e:
            logger.error(f"Failed to send notification for {change.program_handle}: {e}")
    return sent


async def send_startup_message() -> None:
    """Send a startup confirmation message."""
    platforms = ", ".join(config.enabled_platforms)
    msg = (
        "🚀 *Bounties Monitor Started\\!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *Platforms:* {_escape(platforms)}\n"
        f"⏱ *Check interval:* every {config.poll_interval_minutes} minutes\n"
        f"📦 *Data source:* arkadiyt/bounty\\-targets\\-data\n\n"
        "_Watching for new scopes and programs\\.\\.\\._"
    )
    bot = Bot(token=config.telegram_bot_token)
    try:
        await bot.send_message(
            chat_id=config.telegram_chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except TelegramError as e:
        logger.warning(f"Could not send startup message: {e}")


def test_notification() -> bool:
    """Send a test message to verify Telegram is configured correctly."""
    msg = (
        "🔔 *Bounties Monitor \\- Test Notification*\n\n"
        "✅ Telegram is configured correctly\\!\n"
        "_You will receive scope change alerts here\\._"
    )
    return asyncio.run(_send_async(msg))
