#!/bin/bash
# FloodStream VM deployment script
# Run on the DigitalOcean devbox (198.211.98.177)
#
# Usage: ssh dev 'bash -s' < deploy/setup-vm.sh
# Or: ssh dev, then run manually

set -e

REPO_DIR="/root/floodstream"
SERVICE_NAME="floodstream-bot"

echo "=== FloodStream VM Setup ==="

# 1. Clone or pull the repo
if [ -d "$REPO_DIR" ]; then
    echo "Repo exists, pulling latest..."
    cd "$REPO_DIR"
    git pull
else
    echo "Cloning repo..."
    git clone git@github.com:neillgroom/floodstream.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# 2. Set up Python venv and install dependencies
VENV_DIR="$REPO_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv..."
    python3 -m venv "$VENV_DIR"
fi
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -q "python-telegram-bot[job-queue]" pdfplumber pymupdf reportlab supabase httpx

# 3. Check for .env
if [ ! -f "$REPO_DIR/pipeline/.env" ]; then
    echo ""
    echo "WARNING: pipeline/.env not found!"
    echo "Copy it from your local machine:"
    echo "  scp pipeline/.env dev:/root/floodstream/pipeline/.env"
    echo ""
    echo "Required keys:"
    echo "  TELEGRAM_BOT_TOKEN=..."
    echo "  ANTHROPIC_API_KEY=..."
    echo "  ALLOWED_TELEGRAM_USERS=..."
    echo "  SUPABASE_URL=..."
    echo "  SUPABASE_KEY=..."
    echo ""
fi

# 4. Open port 8787 for reset server (if ufw is active)
if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
    echo "Opening port 8787 for reset server..."
    ufw allow 8787/tcp
fi

# 5. Install systemd services (bot + reset server)
echo "Installing systemd services..."
cp "$REPO_DIR/deploy/floodstream-bot.service" /etc/systemd/system/
cp "$REPO_DIR/deploy/reset-server.service" /etc/systemd/system/floodstream-reset.service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl enable floodstream-reset

# 6. Start or restart bot
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Restarting bot..."
    systemctl restart "$SERVICE_NAME"
else
    echo "Starting bot..."
    systemctl start "$SERVICE_NAME"
fi

# 7. Start or restart reset server
if systemctl is-active --quiet floodstream-reset; then
    echo "Restarting reset server..."
    systemctl restart floodstream-reset
else
    echo "Starting reset server..."
    systemctl start floodstream-reset
fi

# 8. Verify
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "=== Bot is running ==="
    systemctl status "$SERVICE_NAME" --no-pager -l
else
    echo ""
    echo "=== Bot FAILED to start ==="
    journalctl -u "$SERVICE_NAME" --no-pager -n 20
    exit 1
fi

echo ""
echo "Useful commands:"
echo "  systemctl status $SERVICE_NAME          # check status"
echo "  journalctl -u $SERVICE_NAME -f          # tail logs"
echo "  bash $REPO_DIR/deploy/restart-bot.sh    # circuit breaker (safe full restart)"
echo "  bash $REPO_DIR/deploy/bot-status.sh     # quick status check"
