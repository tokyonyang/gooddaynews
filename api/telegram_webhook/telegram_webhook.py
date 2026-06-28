from __future__ import annotations

import html
import json
import os
import traceback
from http.server import BaseHTTPRequestHandler
from typing import Any

import requests

VERSION = "echo-diagnostic-2026-06-29-01"


def _json_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def send_json(h: BaseHTTPRequestHandler, status: int, data: dict[str, Any]) -> None:
    body = _json_bytes(data)
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def read_update(h: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(h.headers.get("content-length") or 0)
    if length <= 0:
        return {}
    raw = h.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def get_message(update: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return key, value
    return "unknown", {}


def send_telegram(chat_id: Any, text: str) -> tuple[int, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in Vercel Environment Variables")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code, r.text[:1000]


def secret_status(h: BaseHTTPRequestHandler) -> dict[str, Any]:
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    got = h.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    strict = os.environ.get("TELEGRAM_VERIFY_SECRET", "false").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "strict": strict,
        "expected_set": bool(expected),
        "header_set": bool(got),
        "match": (not expected) or (got == expected),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        send_json(self, 200, {
            "ok": True,
            "service": "gooddaynews-telegram-webhook",
            "version": VERSION,
            "route": "/api/telegram_webhook",
            "env": {
                "TELEGRAM_BOT_TOKEN": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
                "TELEGRAM_CHAT_ID": bool(os.environ.get("TELEGRAM_CHAT_ID")),
                "TELEGRAM_WEBHOOK_SECRET": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET")),
                "TELEGRAM_VERIFY_SECRET": os.environ.get("TELEGRAM_VERIFY_SECRET", "false"),
            },
            "test": "Send /ping to the bot. It should reply immediately.",
        })

    def do_POST(self) -> None:
        try:
            ss = secret_status(self)
            if ss["strict"] and not ss["match"]:
                print("REJECT_SECRET", json.dumps(ss, ensure_ascii=False))
                send_json(self, 403, {"ok": False, "error": "secret mismatch", "secret": ss})
                return

            update = read_update(self)
            update_type, msg = get_message(update)
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            chat_type = chat.get("type")
            text = (msg.get("text") or msg.get("caption") or "").strip()
            print("UPDATE_RECEIVED", json.dumps({
                "version": VERSION,
                "update_type": update_type,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "text": text[:200],
                "secret": ss,
            }, ensure_ascii=False))

            if not chat_id:
                send_json(self, 200, {"ok": True, "skipped": "no chat_id", "update_type": update_type})
                return

            # Diagnostic echo: intentionally bypasses TELEGRAM_CHAT_ID filter.
            if text.lower().startswith("/ping"):
                reply = (
                    "✅ <b>Webhook received</b>\n"
                    f"version: <code>{html.escape(VERSION)}</code>\n"
                    f"update_type: <code>{html.escape(str(update_type))}</code>\n"
                    f"chat_type: <code>{html.escape(str(chat_type))}</code>\n"
                    f"chat_id: <code>{html.escape(str(chat_id))}</code>\n"
                    f"secret_header: <code>{'yes' if ss['header_set'] else 'no'}</code>\n"
                    f"secret_match: <code>{'yes' if ss['match'] else 'no'}</code>"
                )
                status, body = send_telegram(chat_id, reply)
                send_json(self, 200, {"ok": True, "diagnostic": "pong", "telegram_status": status, "telegram_body": body})
                return

            if text.lower().startswith("/topic") or text.startswith("주제:") or text.startswith("토픽:") or text.startswith("핫이슈"):
                topic = text.replace("/topic", "", 1).replace("주제:", "", 1).replace("토픽:", "", 1).replace("핫이슈", "", 1).strip() or "미입력"
                reply = (
                    "🔎 <b>주제 요청 수신 성공</b>\n"
                    f"주제: <b>{html.escape(topic)}</b>\n"
                    f"chat_id: <code>{html.escape(str(chat_id))}</code>\n\n"
                    "이 메시지가 보이면 Telegram → Vercel → Telegram 왕복 연결은 정상입니다. "
                    "다음 단계에서 뉴스/카드뉴스 생성 로직을 다시 연결하면 됩니다."
                )
                status, body = send_telegram(chat_id, reply)
                send_json(self, 200, {"ok": True, "topic": topic, "telegram_status": status, "telegram_body": body})
                return

            # Echo anything else so we can prove webhook activity.
            reply = (
                "ℹ️ <b>Webhook은 정상 수신했습니다.</b>\n"
                "주제 분석은 아래 형식으로 입력하세요.\n"
                "<code>/topic 원달러 환율</code>"
            )
            status, body = send_telegram(chat_id, reply)
            send_json(self, 200, {"ok": True, "echo": True, "telegram_status": status, "telegram_body": body})
        except Exception as e:
            print("WEBHOOK_EXCEPTION", repr(e))
            print(traceback.format_exc())
            # Return 200 so Telegram doesn't keep retrying while we inspect Vercel logs.
            send_json(self, 200, {"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]})
