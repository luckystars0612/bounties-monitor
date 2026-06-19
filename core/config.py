"""
Configuration loader for Bounty Scope Monitor.
Reads settings from .env file and environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # ── Telegram ──────────────────────────────────────────────────────────
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "")
    )

    # ── Polling intervals (minutes) ────────────────────────────────────────
    poll_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_MINUTES", "15"))
    )

    # ── Platforms to enable ───────────────────────────────────────────────
    # Comma-separated list: hackerone,bugcrowd,intigriti,yeswehack
    enabled_platforms: List[str] = field(
        default_factory=lambda: [
            p.strip().lower()
            for p in os.getenv(
                "ENABLED_PLATFORMS", "hackerone,bugcrowd,intigriti,yeswehack"
            ).split(",")
            if p.strip()
        ]
    )

    # ── Data source: arkadiyt/bounty-targets-data ─────────────────────────
    # Raw JSON URLs - updated hourly by the upstream crawler
    data_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DATA_BASE_URL",
            "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data",
        )
    )
    # Optional GitHub token to avoid anonymous rate limits (60 req/hr → 5000 req/hr)
    github_token: str = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN", "")
    )

    # ── Database ───────────────────────────────────────────────────────────
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "bounties_monitor.db")
    )

    # ── Notification filters ───────────────────────────────────────────────
    # Notify on: new_scope, removed_scope, new_program, bounty_increase
    notify_on: List[str] = field(
        default_factory=lambda: [
            e.strip().lower()
            for e in os.getenv(
                "NOTIFY_ON", "new_scope,new_program,bounty_increase,removed_scope"
            ).split(",")
            if e.strip()
        ]
    )

    # Only process / alert for programs offering monetary bounties (skip VDP)
    bounties_only: bool = field(
        default_factory=lambda: os.getenv("BOUNTIES_ONLY", "false").lower() == "true"
    )

    # ── HTTP settings ──────────────────────────────────────────────────────
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )

    def validate(self) -> None:
        """Raise ValueError if critical config is missing."""
        if not self.telegram_bot_token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required. Set it in your .env file."
            )
        if not self.telegram_chat_id:
            raise ValueError(
                "TELEGRAM_CHAT_ID is required. Set it in your .env file.\n"
                "Tip: Message @userinfobot on Telegram to get your Chat ID."
            )


# Singleton instance
config = Config()
