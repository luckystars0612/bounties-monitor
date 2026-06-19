# Bounty Scope Monitor VPS Deployment Guide

This guide explains how to deploy the Bounty Scope Monitor as a **Systemd Service** on a Linux VPS (Ubuntu/Debian, CentOS, etc.), ensuring the bot runs in the background and restarts automatically on system reboots or unexpected crashes.

---

## Step 1: Prepare the VPS Environment

1. Clone the repository onto your VPS:
   ```bash
   git clone https://github.com/luckystars0612/bounties-monitor.git /opt/bounties-monitor
   cd /opt/bounties-monitor
   ```
2. Install **uv** (if you haven't already):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.local/bin/env
   ```
3. Initialize the environment and install dependencies automatically using `uv`:
   ```bash
   uv sync
   ```
4. Copy the environment configuration template and populate it with your settings (Telegram bot token, chat/channel ID, etc.):
   ```bash
   cp .env.example .env
   nano .env
   ```

---

## Step 2: Configure the Systemd Service

1. Copy the systemd service file template into the system configuration directory:
   ```bash
   sudo cp deploy/bounties-monitor.service /etc/systemd/system/bounties-monitor.service
   ```
2. Edit the service file to configure it for your VPS:
   ```bash
   sudo nano /etc/systemd/system/bounties-monitor.service
   ```
   * **Crucial**: Replace `User=YOUR_USERNAME` with your actual VPS Linux user (e.g. `User=ubuntu` or `User=root`).
   * Double check that the paths in `WorkingDirectory` and `ExecStart` match where your project is installed.

3. Reload the systemd configuration to register the new service:
   ```bash
   sudo systemctl daemon-reload
   ```

---

## Step 3: Manage the Service

* **Enable automatic start on VPS boot**:
  ```bash
  sudo systemctl enable bounties-monitor
  ```
* **Start the service**:
  ```bash
  sudo systemctl start bounties-monitor
  ```
* **Stop the service**:
  ```bash
  sudo systemctl stop bounties-monitor
  ```
* **Restart the service** (Do this after updating code or modifying the `.env` file):
  ```bash
  sudo systemctl restart bounties-monitor
  ```
* **Check the running status**:
  ```bash
  sudo systemctl status bounties-monitor
  ```

---

## Step 4: Monitor Logs

You can watch the logs in real-time (to monitor polling cycles, Telegram command inputs, notifications sent, etc.) using:
```bash
journalctl -u bounties-monitor -f
```
