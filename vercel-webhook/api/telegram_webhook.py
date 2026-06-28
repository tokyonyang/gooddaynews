"""Minimal Vercel Telegram webhook for Gooddaynews topic reports.

Deploy with Vercel Root Directory set to: vercel-webhook
Route: /api/telegram_webhook
"""

from __future__ import annotations

import html
import json
import os
import re
import traceback
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests

KST = timezone(timedelta(hours=9))


def env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def jdump(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def send_json(handler: BaseHTTPRequestHandler, status: int, data: dict[str, Any]) -> None:
    body = jdump(data)
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("content-length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def verify_secret(handler: BaseHTTPRequestHandler) -> bool:
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not expected:
        return True
    got = handler.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    return bool(got) and got == expected


def get_message(update: dict[str, Any]) -> dict[str, Any]:
    return (
        update.get("message")
        or update.get("channel_post")
        or update.get("edited_message")
        or update.get("edited_channel_post")
        or {}
    )


def extract_topic(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None

    patterns = [
        r"^/topic(?:@\w+)?\s+(.+)$",
        r"^/토픽(?:@\w+)?\s+(.+)$",
        r"^/주제(?:@\w+)?\s+(.+)$",
        r"^주제\s*[:：]\s*(.+)$",
        r"^토픽\s*[:：]\s*(.+)$",
        r"^핫이슈\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.S)
        if m:
            return m.group(1).strip()[:120]

    if env_bool("TELEGRAM_TOPIC_ACCEPT_PLAIN", "false"):
        if len(text) <= 80 and not text.startswith("/"):
            return text
    return None


def allowed_chat(chat_id: Any) -> bool:
    expected = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not expected:
        return True
    return str(chat_id).strip() == expected


def send_telegram(chat_id: Any, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram sendMessage failed: {r.status_code} {r.text[:500]}")


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=ko&gl=KR&ceid=KR:ko"


def fetch_news(topic: str, limit: int = 8) -> list[dict[str, str]]:
    queries = [
        f"{topic} 경제 영향 OR 시장 OR 증시 OR 환율 OR 금리 OR 유가",
        f"{topic} Reuters OR Bloomberg OR CNBC OR AP economy markets",
        f"{topic} 속보 경제 금융 시장",
    ]
    seen = set()
    items: list[dict[str, str]] = []
    for q in queries:
        try:
            feed = feedparser.parse(google_news_url(q))
            for entry in feed.entries[:12]:
                title = re.sub(r"\s+", " ", getattr(entry, "title", "")).strip()
                link = getattr(entry, "link", "").strip()
                published = getattr(entry, "published", "") or getattr(entry, "updated", "")
                source = "Google News"
                if " - " in title:
                    maybe_title, maybe_source = title.rsplit(" - ", 1)
                    if maybe_source:
                        title = maybe_title.strip()
                        source = maybe_source.strip()
                key = (title.lower(), link)
                if title and key not in seen:
                    seen.add(key)
                    items.append({"title": title, "link": link, "source": source, "published": published})
                if len(items) >= limit:
                    return items
        except Exception:
            continue
    return items[:limit]


def simple_keywords(topic: str) -> list[str]:
    base = [topic]
    related = [
        "경제 영향", "시장 반응", "환율", "금리", "유가", "원자재", "증시", "채권금리",
        "수혜주", "피해주", "인플레이션", "소비자물가", "공급망", "정책 변화",
    ]
    return base + related[:10]


def fallback_report(topic: str, news: list[dict[str, str]]) -> str:
    now = datetime.now(KST).strftime("%m-%d %H:%M")
    esc_topic = html.escape(topic)
    lines: list[str] = []
    lines.append(f"🎯 <b>요청 주제 분석</b>\n주제: <b>{esc_topic}</b>\n기준: {now} KST")
    lines.append("\n🔎 <b>관련 키워드</b>\n" + ", ".join(html.escape(k) for k in simple_keywords(topic)))

    lines.append("\n🔥 <b>관련 핫이슈 TOP 5</b>")
    if news:
        for i, item in enumerate(news[:5], 1):
            title = html.escape(item["title"])
            source = html.escape(item.get("source") or "뉴스")
            link = html.escape(item.get("link") or "")
            lines.append(f"{i}. <b>{title}</b>\n   출처: {source}\n   링크: {link}")
    else:
        lines.append("관련 최신 뉴스를 찾지 못했습니다. 검색어를 조금 더 구체적으로 입력해 주세요.")

    lines.append("\n🃏 <b>카드뉴스 후보</b>")
    card_titles = [
        f"{topic}, 왜 지금 시장이 주목할까?",
        f"{topic}이 환율·금리·물가에 미치는 영향",
        f"{topic} 관련 수혜와 리스크 한눈에 보기",
    ]
    for i, t in enumerate(card_titles, 1):
        lines.append(f"{i}. {html.escape(t)}")

    lines.append("\n🎬 <b>카드뉴스 스크립트</b>")
    script = [
        f"1장: {topic} 이슈 발생, 시장의 관심 집중",
        "2장: 핵심 원인은 정책·수급·지정학·심리 변화",
        "3장: 환율·금리·원자재·증시에 파급 가능성",
        "4장: 개인은 관련 업종과 비용 구조를 함께 확인 필요",
        "5장: 단기 뉴스보다 후속 지표와 공식 발표를 체크",
    ]
    lines.extend(html.escape(s) for s in script)

    lines.append("\n✍️ <b>작성글 후보</b>")
    writing = [
        f"{topic}이 한국 경제와 내 지갑에 미치는 영향 정리",
        f"{topic} 관련주보다 먼저 봐야 할 환율·금리·원자재 체크포인트",
        f"{topic} 이후 시장이 흔들리는 이유와 대응법",
    ]
    for i, t in enumerate(writing, 1):
        lines.append(f"{i}. {html.escape(t)}")
    return "\n".join(lines)


def gemini_report(topic: str, news: list[dict[str, str]]) -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai

        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        client = genai.Client(api_key=api_key)
        news_text = "\n".join(
            f"{i}. {n['title']} / {n.get('source','')} / {n.get('link','')}"
            for i, n in enumerate(news[:8], 1)
        )
        prompt = f"""
너는 한국어 경제/뉴스 큐레이터다. 텔레그램 HTML parse_mode로 보낼 짧은 리포트를 작성하라.
주제: {topic}
뉴스 목록:
{news_text}

조건:
- 3900자 이내
- 한국어
- <b>태그만 사용, Markdown 사용 금지
- 섹션: 🎯 요청 주제 분석, 🔎 관련 키워드, 🔥 관련 핫이슈 TOP 5, 🃏 카드뉴스 후보, 🎬 카드뉴스 스크립트, ✍️ 작성글 후보, 🧾 근거자료
- 제목만 봐도 경제 영향이 보이도록 작성
- 과장 금지. 불확실하면 '가능성'으로 표현
""".strip()
        res = client.models.generate_content(model=model, contents=prompt)
        text = (getattr(res, "text", None) or "").strip()
        return text[:3900] if text else None
    except Exception:
        return None


def build_report(topic: str) -> str:
    limit = int(os.environ.get("TELEGRAM_TOPIC_NEWS_LINKS", "8") or "8")
    news = fetch_news(topic, limit=max(5, min(limit, 12)))
    return gemini_report(topic, news) or fallback_report(topic, news)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        send_json(self, 200, {"ok": True, "service": "gooddaynews-telegram-webhook", "route": "/api/telegram_webhook"})

    def do_POST(self) -> None:
        try:
            if not verify_secret(self):
                send_json(self, 403, {"ok": False, "error": "invalid secret token"})
                return

            update = read_json(self)
            msg = get_message(update)
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = msg.get("text") or msg.get("caption") or ""

            if not chat_id:
                send_json(self, 200, {"ok": True, "skipped": "no chat"})
                return
            if not allowed_chat(chat_id):
                send_json(self, 200, {"ok": True, "skipped": "chat not allowed", "chat_id": chat_id})
                return

            topic = extract_topic(text)
            if not topic:
                send_json(self, 200, {"ok": True, "skipped": "no topic command"})
                return

            send_telegram(chat_id, f"🔎 <b>주제 분석 시작</b>\n주제: <b>{html.escape(topic)}</b>\n잠시만 기다려 주세요.")
            report = build_report(topic)
            send_telegram(chat_id, report)
            send_json(self, 200, {"ok": True, "topic": topic})
        except Exception as e:
            try:
                # Return 200 to avoid endless Telegram retries, but include the error for Vercel logs.
                print("WEBHOOK_ERROR", repr(e))
                print(traceback.format_exc())
            finally:
                send_json(self, 200, {"ok": False, "error": str(e)})
