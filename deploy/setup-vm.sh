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

# 2. Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -q python-telegram-bot pdfplumber pymupdf reportlab supabase 2>/dev/null || \
pip install -q python-telegram-bot pdfplumber pymupdf reportlab supabase

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

# 4. Install systemd service
echo "Installing systemd service..."
cp "$REPO_DIR/deploy/floodstream-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# 5. Start or restart
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Restarting bot..."
    systemctl restart "$SERVICE_NAME"
else
    echo "Starting bot..."
    systemctl start "$SERVICE_NAME"
fi

# 6. Verify
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
echo "  systemctl status $SERVICE_NAME    # check status"
echo "  journalctl -u $SERVICE_NAME -f    # tail logs"
echo "  systemctl restart $SERVICE_NAME   # restart"
echo "  systemctl stop $SERVICE_NAME      # stop"
