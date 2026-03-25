#!/bin/bash
# FloodStream Bot — Circuit Breaker
# Run from phone: ssh dev 'bash /root/floodstream/deploy/restart-bot.sh'
# Or from tmux:   bash ~/floodstream/deploy/restart-bot.sh
#
# What it does:
# 1. Stops the systemd service
# 2. Kills any orphan bot processes
# 3. Clears the Telegram polling session via API
# 4. Resets systemd failure counter
# 5. Starts the service fresh
# 6. Shows status

set -e

echo "=== FloodStream Circuit Breaker ==="
echo ""

# 1. Stop service
echo "[1/5] Stopping service..."
systemctl stop floodstream-bot 2>/dev/null || true
sleep 2

# 2. Kill any orphan python processes running bot.py
echo "[2/5] Killing orphan processes..."
pkill -f "python.*bot.py" 2>/dev/null || true
sleep 1

# 3. Clear Telegram polling session
echo "[3/5] Clearing Telegram session..."
BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN /root/floodstream/pipeline/.env | cut -d= -f2 | tr -d ' "'"'"'')
if [ -n "$BOT_TOKEN" ]; then
    RESULT=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true")
    echo "    Telegram: $RESULT"
else
    echo "    WARNING: Could not read bot token from .env"
fi
sleep 2

# 4. Reset systemd failure counter
echo "[4/5] Resetting failure counter..."
systemctl reset-failed floodstream-bot 2>/dev/null || true

# 5. Start service
echo "[5/5] Starting service..."
systemctl start floodstream-bot

# Wait for it to stabilize
sleep 3

# Show status
echo ""
echo "=== Status ==="
systemctl is-active floodstream-bot && echo "Bot is RUNNING" || echo "Bot FAILED to start — check: journalctl -u floodstream-bot -n 20"
echo ""
echo "Recent logs:"
journalctl -u floodstream-bot -n 5 --no-pager 2>/dev/null || echo "(no logs yet)"
