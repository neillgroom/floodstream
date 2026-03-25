"""
FloodStream Reset Server — Bulletproof circuit breaker endpoint.

Runs as a SEPARATE systemd service from the bot. When the bot is dead,
this is still alive and waiting for Neill's phone to hit it.

One endpoint: POST /reset with Authorization header → runs restart-bot.sh
"""

import http.server
import json
import os
import subprocess
import threading
from datetime import datetime, timezone

PORT = 8787
# Shared secret — must match the HTML page. Not military-grade, but prevents drive-by resets.
RESET_TOKEN = os.environ.get("RESET_TOKEN", "floodstream-reset-2026")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESTART_SCRIPT = os.path.join(SCRIPT_DIR, "restart-bot.sh")
STATUS_SCRIPT = os.path.join(SCRIPT_DIR, "bot-status.sh")
TELEGRAM_RESTART_SCRIPT = os.path.join(SCRIPT_DIR, "restart-telegram.sh")
TELEGRAM_STATUS_SCRIPT = os.path.join(SCRIPT_DIR, "telegram-status.sh")
HTML_FILE = os.path.join(SCRIPT_DIR, "reset.html")


class ResetHandler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _auth_ok(self):
        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        return token == RESET_TOKEN

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            try:
                with open(HTML_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self._json(404, {"error": "reset.html not found"})
            return

        if self.path == "/ping":
            self._json(200, {"status": "ok", "service": "floodstream-reset-server"})
            return

        if self.path == "/status":
            if not self._auth_ok():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                result = subprocess.run(
                    ["bash", STATUS_SCRIPT],
                    capture_output=True, text=True, timeout=10
                )
                self._json(200, {"output": result.stdout.strip()})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        if self.path == "/telegram-status":
            if not self._auth_ok():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                result = subprocess.run(
                    ["bash", TELEGRAM_STATUS_SCRIPT],
                    capture_output=True, text=True, timeout=10
                )
                self._json(200, {"output": result.stdout.strip()})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return

        self._json(404, {"error": "not found"})

    def do_POST(self):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if not self._auth_ok():
            self._json(401, {"error": "unauthorized"})
            return

        if self.path == "/reset":
            script = RESTART_SCRIPT
        elif self.path == "/telegram-reset":
            script = TELEGRAM_RESTART_SCRIPT
        else:
            self._json(404, {"error": "not found"})
            return

        try:
            result = subprocess.run(
                ["bash", script],
                capture_output=True, text=True, timeout=30
            )
            self._json(200, {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "errors": result.stderr.strip() if result.stderr else None,
                "timestamp": timestamp,
            })
        except subprocess.TimeoutExpired:
            self._json(504, {"error": "restart timed out (30s)", "timestamp": timestamp})
        except Exception as e:
            self._json(500, {"error": str(e), "timestamp": timestamp})

    def log_message(self, format, *args):
        # Quieter logging — just method + path + status
        pass


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), ResetHandler)
    print(f"Reset server running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down")
        server.shutdown()
