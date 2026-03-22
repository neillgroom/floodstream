#!/bin/bash
# Quick bot status check — run from phone: ssh dev 'bash /root/floodstream/deploy/bot-status.sh'
systemctl is-active floodstream-bot >/dev/null 2>&1 && echo "✅ BOT RUNNING" || echo "❌ BOT DOWN"
echo "Uptime: $(systemctl show floodstream-bot --property=ActiveEnterTimestamp --value 2>/dev/null || echo 'unknown')"
echo "Last 3 logs:"
journalctl -u floodstream-bot -n 3 --no-pager 2>/dev/null || echo "(no logs)"
