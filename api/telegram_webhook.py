"""Vercel Telegram webhook endpoint.

Route after deployment:
  https://<your-vercel-domain>/api/telegram_webhook

Telegram -> Vercel -> topic report -> Telegram reply.
"""

import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

# Make repository root importable when Vercel executes this file from /api.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from telegram_topic_listener import (  # noqa: E402
    _allowed_chat,
    _build_topic_report,
    _extract_topic,
    _html,
    _message_from_update,
    _send_message,
)

# Best-effort duplicate guard for warm serverless instances.
# Telegram retries webhook updates when a request times out or returns non-2xx.
_PROCESSED_UPDATES: dict[int, float] = {}
_DEDUPE_TTL_SECONDS = 60 * 30


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or 0)
    if length <= 0:
        return {}
    body = handler.rfile.read(length)
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_authorized_request(handler: BaseHTTPRequestHandler) -> bool:
    """Validate Telegram's optional webhook secret token.

    Set TELEGRAM_WEBHOOK_SECRET in both Vercel and Telegram setWebhook.
    Telegram then sends X-Telegram-Bot-Api-Secret-Token on every webhook request.
    """
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not expected:
        return True
    received = handler.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    return bool(received) and received == expected


def _mark_duplicate(update_id: int | None) -> bool:
    if update_id is None:
        return False
    now = time.time()
    expired = [k for k, ts in _PROCESSED_UPDATES.items() if now - ts > _DEDUPE_TTL_SECONDS]
    for k in expired:
        _PROCESSED_UPDATES.pop(k, None)
    if update_id in _PROCESSED_UPDATES:
        return True
    _PROCESSED_UPDATES[update_id] = now
    return False


def _handle_help(token: str, chat_id: str | int) -> None:
    accept_plain = _env_true("TELEGRAM_TOPIC_ACCEPT_PLAIN", "false")
    examples = [
        "/topic 원달러 환율",
        "/topic 국제유가 급등",
        "주제: 엔비디아 실적",
        "핫이슈 트럼프 관세",
    ]
    if accept_plain:
        examples.append("원달러 환율")
    message = (
        "🤖 <b>GooddayNews 주제 분석 봇</b>\n\n"
        "아래처럼 텔레그램에 주제를 보내면 관련 핫이슈, 키워드, 카드뉴스 후보, "
        "카드뉴스 스크립트, 작성글 후보를 다시 정리해드립니다.\n\n"
        + "\n".join(f"• <code>{_html(x)}</code>" for x in examples)
    )
    _send_message(token, chat_id, message, parse_mode="HTML")


def _process_update(update: dict[str, Any]) -> tuple[bool, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN is not set"

    update_id = update.get("update_id")
    if isinstance(update_id, int) and _mark_duplicate(update_id):
        return True, "duplicate_skipped"

    msg = _message_from_update(update)
    if not msg:
        return True, "no_message"

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return True, "no_chat_id"
    if not _allowed_chat(chat_id):
        return True, "chat_not_allowed"

    text = msg.get("text") or msg.get("caption") or ""
    compact = re.sub(r"\s+", " ", str(text or "")).strip()

    if compact.lower() in {"/start", "/help", "help", "도움말"}:
        _handle_help(token, chat_id)
        return True, "help_sent"

    topic = _extract_topic(compact)
    if not topic:
        return True, "no_topic"

    _send_message(
        token,
        chat_id,
        f"🧭 <b>주제 분석을 시작합니다.</b>\n요청 주제: <b>{_html(topic)}</b>\n잠시만 기다려주세요.",
        parse_mode="HTML",
    )

    try:
        report = _build_topic_report(topic)
        _send_message(token, chat_id, report, parse_mode="HTML")
        return True, "topic_report_sent"
    except Exception as exc:
        err = re.sub(r"\s+", " ", str(exc)).strip()[:600]
        _send_message(
            token,
            chat_id,
            f"❌ 주제 분석 중 오류가 발생했습니다.\n<code>{_html(err)}</code>",
            parse_mode="HTML",
        )
        return False, err


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        _json_response(self, 200, {
            "ok": True,
            "service": "gooddaynews-telegram-webhook",
            "usage": "POST Telegram webhook updates to this endpoint.",
        })

    def do_POST(self) -> None:
        if not _is_authorized_request(self):
            _json_response(self, 401, {"ok": False, "error": "unauthorized_webhook_secret"})
            return

        try:
            update = _read_json(self)
        except Exception as exc:
            _json_response(self, 400, {"ok": False, "error": f"invalid_json: {exc}"})
            return

        try:
            ok, status = _process_update(update)
            # Telegram only needs a 2xx response to stop retrying.
            _json_response(self, 200, {"ok": bool(ok), "status": status})
        except Exception as exc:
            # Return 200 after trying to report the error, otherwise Telegram may retry and duplicate work.
            _json_response(self, 200, {"ok": False, "status": "handler_error", "error": str(exc)[:500]})
