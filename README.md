# bounties-monitor 🎯

A lightweight VPS service that monitors bug bounty platforms for **new scope additions**, **new programs**, and **bounty increases** — and sends instant **Telegram notifications**.

**Data source:** [`arkadiyt/bounty-targets-data`](https://github.com/arkadiyt/bounty-targets-data) — updated hourly via GitHub Actions. No platform API keys or scraping required.

---

## Features

| Event | Description |
|---|---|
| ✅ New scope | A target domain/asset was added to a program |
| ❌ Removed scope | A target was removed from a program |
| 🎉 New program | A new bug bounty program went public |
| 💰 Bounty increase | Maximum payout was raised |

**Platforms covered:** HackerOne · Bugcrowd · Intigriti · YesWeHack

---

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) — fast Python package manager
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Your Telegram chat ID (message [@userinfobot](https://t.me/userinfobot))

---

## Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/your-username/bounties-monitor.git
cd bounties-monitor

# Create virtual environment and install packages
uv venv
uv pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in the required values:

```env
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>
```

### 3. Test Telegram connection

```bash
uv run python main.py --test
```

### 4. Run a single poll cycle (build initial snapshot)

```bash
uv run python main.py --run-once
```

### 5. Start the daemon

```bash
uv run python main.py
```

---

## Configuration

All settings are in `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | — | Your chat or group ID |
| `POLL_INTERVAL_MINUTES` | | `60` | How often to check for updates |
| `ENABLED_PLATFORMS` | | all | `hackerone,bugcrowd,intigriti,yeswehack` |
| `NOTIFY_ON` | | all | `new_scope,new_program,bounty_increase,removed_scope` |
| `GITHUB_TOKEN` | | — | Optional — raises rate limit from 60→5000 req/hr |
| `DATABASE_PATH` | | `bounties_monitor.db` | SQLite file path |

---

## Deploy as a systemd service (VPS)

```bash
# Copy the unit file
sudo cp deploy/bounties-monitor.service /etc/systemd/system/

# Edit User and WorkingDirectory to match your setup
sudo nano /etc/systemd/system/bounties-monitor.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now bounties-monitor

# View live logs
sudo journalctl -u bounties-monitor -f
```

---

## Project structure

```
bounties-monitor/
├── main.py              # Entry point & scheduler
├── requirements.txt
├── .env                 # Secrets (never commit)
├── .env.example         # Config template
│
├── core/
│   ├── config.py        # Load settings from .env
│   ├── models.py        # Dataclasses: Program, ScopeItem, ScopeChange
│   ├── database.py      # SQLite via SQLAlchemy
│   ├── fetcher.py       # Download JSON from bounty-targets-data
│   ├── diff_engine.py   # Compare old vs new snapshots
│   ├── notifier.py      # Format & send Telegram messages
│   └── processor.py     # Orchestrate the full poll cycle
│
├── deploy/
│   └── bounties-monitor.service   # systemd unit
│
└── logs/                # Rotating log files (auto-created)
```

---

## How it works

```
arkadiyt/bounty-targets-data  (GitHub, updated hourly)
        │
        │  fetcher.py  — downloads hackerone_data.json, bugcrowd_data.json, etc.
        ▼
   Parse into Program + ScopeItem objects
        │
        │  diff_engine.py  — compare with previous SQLite snapshot
        ▼
   Detect: new scopes / removed scopes / new programs / bounty changes
        │
        │  notifier.py  — format Telegram MarkdownV2 message
        ▼
   Send instant Telegram alert  📱
        │
        │  database.py  — persist new snapshot for next cycle
        ▼
   Sleep until next poll
```

---

## Example Telegram notification

```
🟠 [HackerOne] New Scope Added
📌 Tesla
━━━━━━━━━━━━━━━━━━━━━━
✅ New In-Scope Targets:
  ▸ *.tesla.com [💰] critical
  ▸ api.tesla.com [💰] high

⏰ 2026-06-19 10:00 UTC
```

---

## CLI reference

```bash
uv run python main.py              # Daemon mode (scheduler)
uv run python main.py --test       # Send a test Telegram message
uv run python main.py --run-once   # Run one cycle and exit
```