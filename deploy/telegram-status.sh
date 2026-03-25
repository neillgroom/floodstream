#!/bin/bash
# Quick telegram-bot status via pm2 + webhook check
BOT_TOKEN="8554034779:AAF_bNLmaGOapRBnrdBTkGYKuPYgpoDzu1I"

PM2_OK=false
pm2 jlist 2>/dev/null | python3 -c "
import sys, json
procs = json.load(sys.stdin)
bot = next((p for p in procs if p['name'] == 'telegram-bot'), None)
if not bot:
    print('telegram-bot not found in pm2')
    sys.exit(1)
status = bot['pm2_env']['status']
restarts = bot['pm2_env']['restart_time']
pid = bot['pid']
print(f'PM2: {status.upper()} (PID {pid}, restarts: {restarts})')
sys.exit(0 if status == 'online' else 1)
" 2>/dev/null && PM2_OK=true

# Verify the webhook is registered
WEBHOOK_URL=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('url',''))" 2>/dev/null)

if [ "$PM2_OK" = true ] && [ -n "$WEBHOOK_URL" ]; then
  echo "RUNNING"
elif [ "$PM2_OK" = true ] && [ -z "$WEBHOOK_URL" ]; then
  echo "PM2 online but WEBHOOK MISSING"
  echo "OFFLINE"
else
  echo "OFFLINE"
fi
