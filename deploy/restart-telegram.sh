#!/bin/bash
# Telegram Bot — Circuit Breaker via pm2
# Restarts the bot AND re-registers the webhook
set -e

BOT_TOKEN="8554034779:AAF_bNLmaGOapRBnrdBTkGYKuPYgpoDzu1I"
WEBHOOK_URL="https://thetower.one/telegram-webhook"
WEBHOOK_SECRET="droplet_webhook_secret_2024"

echo "=== Telegram Bot Restart ==="
echo ""

echo "[1/3] Restarting via pm2..."
pm2 restart telegram-bot
sleep 3

echo "[2/3] Registering webhook..."
RESULT=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook"   -d "url=${WEBHOOK_URL}"   -d "secret_token=${WEBHOOK_SECRET}"   -d 'allowed_updates=["message"]')
echo "    Webhook: $RESULT"
sleep 1

echo "[3/3] Verifying..."
VERIFY=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -c "
import sys, json
d = json.load(sys.stdin)
url = d.get('result',{}).get('url','')
if url:
    print(f'WEBHOOK ACTIVE: {url}')
else:
    print('WEBHOOK MISSING - check for conflicts')
" 2>/dev/null)
echo "    $VERIFY"

STATUS=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
procs = json.load(sys.stdin)
bot = next((p for p in procs if p['name'] == 'telegram-bot'), None)
if bot:
    print(f"status={bot['pm2_env']['status']} restarts={bot['pm2_env']['restart_time']}")
else:
    print('telegram-bot not found in pm2')
" 2>/dev/null || echo "could not parse pm2 status")
echo "    PM2: $STATUS"
