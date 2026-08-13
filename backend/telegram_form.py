#!/usr/bin/env python3
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 3102
MAX_BODY_SIZE = 10_000
RATE_LIMIT_SECONDS = 30
ALLOWED_METHODS = {"Телефон", "WA", "Telegram"}
TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")
CHAT_ID_PATTERN = re.compile(r"^-?\d+$")
last_submissions: dict[str, float] = {}


class FormHandler(BaseHTTPRequestHandler):
    server_version = ""
    sys_version = ""

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/contact":
            self.send_json(404, {"ok": False})
            return

        content_type = self.headers.get("Content-Type", "").lower()
        if not content_type.startswith("application/json"):
            self.send_json(415, {"ok": False})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"ok": False})
            return
        if content_length <= 0 or content_length > MAX_BODY_SIZE:
            self.send_json(413, {"ok": False})
            return

        try:
            data = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"ok": False})
            return
        if not isinstance(data, dict):
            self.send_json(400, {"ok": False})
            return

        name = str(data.get("name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        method = str(data.get("method", "")).strip()
        question = str(data.get("question", "")).strip()
        newsletter = data.get("newsletter") is True
        if (
            not name
            or len(name) > 100
            or not phone
            or len(phone) > 50
            or method not in ALLOWED_METHODS
            or len(question) > 2000
        ):
            self.send_json(422, {"ok": False})
            return

        client_ip = self.headers.get("X-Real-IP", self.client_address[0])
        now = time.monotonic()
        if now - last_submissions.get(client_ip, 0) < RATE_LIMIT_SECONDS:
            self.send_json(429, {"ok": False})
            return

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not TOKEN_PATTERN.fullmatch(token) or not CHAT_ID_PATTERN.fullmatch(chat_id):
            self.log_error("Telegram environment variables are missing or invalid")
            self.send_json(503, {"ok": False})
            return

        message = (
            "🔥 Новая заявка с сайта!\n\n"
            f"👤 Имя: {name}\n"
            f"📞 Телефон: {phone}\n"
            f"💬 Связь: {method}\n"
            f"❓ Вопрос: {question or 'Нет'}\n"
            f"📬 Рассылка: {'Да' if newsletter else 'Нет'}"
        )
        payload = json.dumps(
            {"chat_id": chat_id, "text": message}, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=7) as response:
                success = 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError) as error:
            self.log_error("Telegram request failed: %s", error)
            success = False

        if not success:
            self.send_json(502, {"ok": False})
            return

        last_submissions[client_ip] = now
        self.send_json(200, {"ok": True})

    def do_GET(self) -> None:
        self.send_json(405, {"ok": False})

    def log_message(self, format_string: str, *args: object) -> None:
        super().log_message(format_string, *args)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), FormHandler).serve_forever()
