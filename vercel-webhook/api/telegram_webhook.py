from __future__ import annotations

import html
import os
import traceback
from typing import Any

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
VERSION = "flask-diagnostic-2026-06-29-02"


def _env_flag(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _telegram_send(chat_id: Any, text: str) -> tuple[int, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return 0, "TELEGRAM_BOT_TOKEN is missing"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    return r.status_code, r.text[:1000]


def _extract_message(update: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return key, value
    return "unknown", {}


def _secret_info() -> dict[str, Any]:
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    strict = os.environ.get("TELEGRAM_VERIFY_SECRET", "false").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "strict": strict,
        "expected_set": bool(expected),
        "header_set": bool(got),
        "match": (not expected) or (got == expected),
    }


@app.route("/", methods=["GET", "POST"])
@app.route("/api/telegram_webhook", methods=["GET", "POST"])
@app.route("/<path:_path>", methods=["GET", "POST"])
def telegram_webhook(_path: str = ""):
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "service": "gooddaynews-telegram-webhook",
            "version": VERSION,
            "route": "/api/telegram_webhook",
            "method": "GET",
            "env": {
                "TELEGRAM_BOT_TOKEN": _env_flag("TELEGRAM_BOT_TOKEN"),
                "TELEGRAM_CHAT_ID": _env_flag("TELEGRAM_CHAT_ID"),
                "TELEGRAM_WEBHOOK_SECRET": _env_flag("TELEGRAM_WEBHOOK_SECRET"),
                "TELEGRAM_VERIFY_SECRET": os.environ.get("TELEGRAM_VERIFY_SECRET", "false"),
            },
            "test": "Send /ping to the bot. It should reply immediately.",
        })

    try:
        ss = _secret_info()
        if ss["strict"] and not ss["match"]:
            return jsonify({"ok": False, "error": "secret mismatch", "secret": ss}), 403

        update = request.get_json(silent=True) or {}
        update_type, msg = _extract_message(update)
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        chat_type = chat.get("type")
        text = (msg.get("text") or msg.get("caption") or "").strip()

        print("UPDATE_RECEIVED", {
            "version": VERSION,
            "update_type": update_type,
            "chat_id": chat_id,
            "chat_type": chat_type,
            "text": text[:200],
            "secret": ss,
        })

        if not chat_id:
            return jsonify({"ok": True, "skipped": "no chat_id", "update_type": update_type})

        lower = text.lower()
        if lower.startswith("/ping"):
            reply = (
                "✅ <b>Webhook received</b>\n"
                f"version: <code>{html.escape(VERSION)}</code>\n"
                f"update_type: <code>{html.escape(str(update_type))}</code>\n"
                f"chat_type: <code>{html.escape(str(chat_type))}</code>\n"
                f"chat_id: <code>{html.escape(str(chat_id))}</code>\n"
                f"secret_header: <code>{'yes' if ss['header_set'] else 'no'}</code>\n"
                f"secret_match: <code>{'yes' if ss['match'] else 'no'}</code>"
            )
            status, body = _telegram_send(chat_id, reply)
            return jsonify({"ok": True, "diagnostic": "pong", "telegram_status": status, "telegram_body": body})

        if lower.startswith("/topic") or text.startswith("주제:") or text.startswith("토픽:") or text.startswith("핫이슈"):
            topic = text.replace("/topic", "", 1).replace("주제:", "", 1).replace("토픽:", "", 1).replace("핫이슈", "", 1).strip() or "미입력"
            reply = (
                "🔎 <b>주제 요청 수신 성공</b>\n"
                f"주제: <b>{html.escape(topic)}</b>\n"
                f"chat_id: <code>{html.escape(str(chat_id))}</code>\n\n"
                "이 메시지가 보이면 Telegram → Vercel → Telegram 왕복 연결은 정상입니다."
            )
            status, body = _telegram_send(chat_id, reply)
            return jsonify({"ok": True, "topic": topic, "telegram_status": status, "telegram_body": body})

        reply = (
            "ℹ️ <b>Webhook은 정상 수신했습니다.</b>\n"
            "주제 분석은 아래 형식으로 입력하세요.\n"
            "<code>/topic 원달러 환율</code>"
        )
        status, body = _telegram_send(chat_id, reply)
        return jsonify({"ok": True, "echo": True, "telegram_status": status, "telegram_body": body})
    except Exception as e:
        print("WEBHOOK_EXCEPTION", repr(e))
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()[-1500:]}), 200
