from __future__ import annotations

import html
import json
import os
import re
import time
import traceback
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
VERSION = "topic-report-flask-2026-06-29-01"

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

STOPWORDS = {
    "속보", "단독", "종합", "사진", "영상", "뉴스", "관련", "오늘", "내일", "이번", "지난", "기자", "공식",
    "발표", "확인", "가능성", "영향", "전망", "시장", "경제", "글로벌", "한국", "미국", "중국", "정부",
    "after", "before", "with", "from", "that", "this", "will", "says", "said", "amid", "over", "into",
    "reuters", "bloomberg", "cnbc", "business", "markets", "breaking", "news", "global", "economy",
}


def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return default


def _h(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _ha(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _telegram_send(chat_id: Any, text: str, parse_mode: str | None = "HTML") -> tuple[int, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return 0, "TELEGRAM_BOT_TOKEN is missing"

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    chunks = _split_telegram_text(text)
    last_status, last_body = 0, ""
    for chunk in chunks:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(url, json=payload, timeout=25)
        last_status, last_body = resp.status_code, resp.text[:1000]
        if resp.status_code >= 400:
            print("TELEGRAM_SEND_FAILED", resp.status_code, resp.text[:1000])
            break
        time.sleep(0.15)
    return last_status, last_body


def _split_telegram_text(text: str, limit: int = 3800) -> list[str]:
    text = str(text or "")
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n"):
        candidate = current + ("\n" if current else "") + block
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    out: list[str] = []
    for c in chunks:
        if len(c) <= limit:
            out.append(c)
        else:
            out.extend(c[i : i + limit] for i in range(0, len(c), limit))
    return out


def _extract_message(update: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return key, value
    return "unknown", {}


def _secret_info() -> dict[str, Any]:
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "").strip()
    strict = _env_bool("TELEGRAM_VERIFY_SECRET", "false")
    return {
        "strict": strict,
        "expected_set": bool(expected),
        "header_set": bool(got),
        "match": (not expected) or (got == expected),
    }


def _extract_topic(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    patterns = [
        r"^/topic(?:@\w+)?\s+(.+)$",
        r"^/issue(?:@\w+)?\s+(.+)$",
        r"^/hot(?:@\w+)?\s+(.+)$",
        r"^/keyword(?:@\w+)?\s+(.+)$",
        r"^/(?:주제|토픽|이슈)(?:@\w+)?\s+(.+)$",
        r"^(?:주제|토픽|이슈|핫이슈|키워드)\s*[:：]?\s+(.+)$",
    ]
    for pat in patterns:
        m = re.match(pat, text, flags=re.I)
        if m:
            return m.group(1).strip()[:120]
    if _env_bool("TELEGRAM_TOPIC_ACCEPT_PLAIN", "false") and not text.startswith("/") and len(text) <= 120:
        return text
    return ""


def _published_dt(entry: Any) -> datetime:
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None) or entry.get(key) if isinstance(entry, dict) else None
        if value:
            try:
                return parsedate_to_datetime(value).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc) - timedelta(days=365)


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    title = re.sub(r"\s+-\s+[^-]{2,35}$", "", title).strip()
    return title[:140]


def _google_news_rss(query: str, *, geo: str = "KR", hl: str = "ko", limit: int = 8) -> list[dict[str, Any]]:
    q = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={geo}&ceid={geo}:{hl}"
    feed = feedparser.parse(url)
    items: list[dict[str, Any]] = []
    for entry in feed.entries[: max(limit * 2, limit)]:
        title = _clean_title(getattr(entry, "title", "") or entry.get("title", ""))
        link = getattr(entry, "link", "") or entry.get("link", "")
        source_obj = getattr(entry, "source", None) or entry.get("source", {})
        source = ""
        if isinstance(source_obj, dict):
            source = source_obj.get("title", "")
        else:
            source = getattr(source_obj, "title", "") if source_obj else ""
        dt = _published_dt(entry)
        if title and link:
            items.append({
                "title": title,
                "url": link,
                "source": source or "Google News",
                "published_dt": dt,
                "published": dt.astimezone(timezone(timedelta(hours=9))).strftime("%m-%d %H:%M"),
                "query": query,
            })
    return items[:limit]


def _fetch_articles(topic: str) -> list[dict[str, Any]]:
    geo = os.environ.get("GOOGLE_NEWS_GEO", "KR").strip() or "KR"
    hl = os.environ.get("GOOGLE_NEWS_HL", "ko").strip() or "ko"
    limit = _env_int("TELEGRAM_TOPIC_NEWS_LINKS", 8)
    queries = [
        topic,
        f"{topic} 경제 영향",
        f"{topic} 시장 전망",
        f"{topic} Reuters Bloomberg markets economy",
    ]
    if _env_bool("TELEGRAM_TOPIC_INCLUDE_GLOBAL_BREAKING", "true"):
        queries.extend([
            "Reuters breaking news global economy markets",
            "Bloomberg breaking news markets economy",
        ])

    seen: set[str] = set()
    articles: list[dict[str, Any]] = []
    per_query = max(3, min(6, limit))
    for query in queries:
        try:
            for item in _google_news_rss(query, geo=geo, hl=hl, limit=per_query):
                key = item.get("url") or item.get("title")
                if key in seen:
                    continue
                seen.add(str(key))
                articles.append(item)
        except Exception as exc:
            print("RSS_FETCH_ERROR", query, repr(exc))
    articles.sort(key=lambda x: x.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return articles[: max(limit, 8)]


def _extract_keywords(topic: str, articles: list[dict[str, Any]], max_keywords: int = 12) -> list[str]:
    score: dict[str, int] = {}
    for part in re.split(r"[\s,/·]+", topic):
        part = part.strip()
        if len(part) >= 2:
            score[part] = score.get(part, 0) + 20
    for idx, article in enumerate(articles):
        title = article.get("title", "")
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", title):
            t = token.strip()
            if not t or t.isdigit() or len(t) > 24:
                continue
            if t.lower() in STOPWORDS or t in STOPWORDS:
                continue
            score[t] = score.get(t, 0) + max(1, 10 - idx)
    ranked = sorted(score.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for k, _ in ranked:
        norm = k.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(k)
        if len(out) >= max_keywords:
            break
    return out


def _extract_json(text: str) -> Any:
    text = str(text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return None


def _gemini_plan(topic: str, articles: list[dict[str, Any]], keywords: list[str]) -> dict[str, Any] | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    article_lines = []
    for i, a in enumerate(articles[:10], 1):
        article_lines.append(f"{i}. {a.get('title')} / {a.get('source')} / {a.get('published')}")
    prompt = f"""
너는 한국어 뉴스/애드센스/카드뉴스 기획자다.
텔레그램으로 들어온 주제에 대해 관련 기사 제목을 바탕으로 리포트를 만든다.
과장하지 말고 기사 제목에서 확인 가능한 범위 안에서만 작성한다. 투자 조언처럼 확정하지 않는다.
제목만 봐도 어떤 정보가 들어 있는지 알 수 있게 쓴다.

[요청 주제]
{topic}

[키워드 후보]
{', '.join(keywords)}

[관련 기사]
{chr(10).join(article_lines)}

아래 JSON만 반환해라.
{{
  "summary_title": "한국어 리포트 제목",
  "related_keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5", "키워드6"],
  "hot_issues": [
    {{"title": "관련 핫이슈 제목", "why": "경제/시장/생활에 왜 중요한지 1문장", "keywords": ["키워드", "키워드"]}}
  ],
  "card_news_candidates": [
    {{"title": "카드뉴스 후보 제목", "angle": "카드뉴스 소구점", "target": "읽을 사람"}}
  ],
  "card_news_script": [
    {{"page": 1, "headline": "1장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 2, "headline": "2장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 3, "headline": "3장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 4, "headline": "4장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 5, "headline": "5장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 6, "headline": "6장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}}
  ],
  "article_candidates": [
    {{"seo_title": "검색 유입형 글 제목", "main_keyword": "메인 키워드", "sub_keywords": ["보조", "키워드"], "angle": "글 방향"}}
  ]
}}
""".strip()
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=model, contents=prompt)
        data = _extract_json(resp.text or "")
        if isinstance(data, dict):
            return data
    except Exception as exc:
        print("GEMINI_ERROR", repr(exc))
    return None


def _fallback_plan(topic: str, articles: list[dict[str, Any]], keywords: list[str]) -> dict[str, Any]:
    hot = []
    for article in articles[:5]:
        title = article.get("title", "")
        if title:
            hot.append({
                "title": title,
                "why": "최근 기사에서 확인되는 관련 이슈로, 검색 유입과 카드뉴스 소재로 활용하기 좋습니다.",
                "keywords": keywords[:4],
            })
    if not hot:
        hot.append({"title": f"{topic} 관련 최신 이슈 정리", "why": "사용자가 직접 요청한 주제입니다.", "keywords": keywords[:4]})
    return {
        "summary_title": f"{topic} 관련 핫이슈·카드뉴스·작성글 후보",
        "related_keywords": keywords[:10],
        "hot_issues": hot,
        "card_news_candidates": [
            {"title": f"{topic}, 지금 왜 주목받나", "angle": "배경 → 영향 → 체크포인트를 한눈에 보여주는 정보형 카드뉴스", "target": "뉴스를 빠르게 이해하고 싶은 독자"},
            {"title": f"{topic} 핵심 키워드 5가지", "angle": "복잡한 이슈를 키워드 중심으로 쪼개는 요약형 카드뉴스", "target": "블로그·인스타 유입 독자"},
            {"title": f"{topic}이 내 지갑에 미치는 영향", "angle": "생활비·투자심리·소비자 관점의 실용형 카드뉴스", "target": "생활경제 관심 독자"},
        ],
        "card_news_script": [
            {"page": 1, "headline": f"{topic}, 왜 지금 주목받나", "body": "최근 관련 뉴스에서 이 주제가 다시 부각되고 있습니다.", "visual": "큰 제목과 키워드 구름"},
            {"page": 2, "headline": "핵심 키워드", "body": f"핵심은 {', '.join(keywords[:4]) or topic}입니다.", "visual": "키워드 4개 카드 배치"},
            {"page": 3, "headline": "경제에 미치는 영향", "body": "가격, 환율, 투자심리, 정책 기대에 영향을 줄 수 있습니다.", "visual": "영향 연결도"},
            {"page": 4, "headline": "관련 기사 흐름", "body": "최근 기사 제목을 보면 시장이 어떤 포인트에 반응하는지 볼 수 있습니다.", "visual": "뉴스 타임라인"},
            {"page": 5, "headline": "확인할 체크포인트", "body": "공식 발표, 후속 기사, 수치 변화, 시장 반응을 함께 확인해야 합니다.", "visual": "체크리스트"},
            {"page": 6, "headline": "한 줄 정리", "body": "이슈 자체보다 원인과 파급효과를 함께 보는 것이 중요합니다.", "visual": "요약 문장 중심 마무리"},
        ],
        "article_candidates": [
            {"seo_title": f"{topic} 최신 이슈 정리, 왜 지금 주목해야 할까", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "배경·원인·영향을 정리하는 해설형 글"},
            {"seo_title": f"{topic} 관련 키워드와 경제 영향 한눈에 보기", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "키워드 중심 검색 유입형 글"},
            {"seo_title": f"{topic}이 생활경제에 미치는 영향", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "생활경제 관점의 실용형 글"},
        ],
    }


def _news_links(articles: list[dict[str, Any]], limit: int = 8) -> str:
    if not articles:
        return "최근 기준 확인된 기사 링크가 없습니다."
    lines = []
    for i, a in enumerate(articles[:limit], 1):
        title = _h(a.get("title", "기사 제목 없음"))
        source = _h(a.get("source", ""))
        published = _h(a.get("published", ""))
        url = str(a.get("url") or "")
        meta = " · ".join(x for x in [source, published] if x)
        link = f'<a href="{_ha(url)}">링크{i}</a>' if url.startswith("http") else f"링크{i}"
        lines.append(f"  {i}) {title}" + (f" ({meta})" if meta else "") + f" / {link}")
    return "\n".join(lines)


def _build_report(topic: str) -> str:
    articles = _fetch_articles(topic)
    keywords = _extract_keywords(topic, articles)
    plan = _gemini_plan(topic, articles, keywords) or _fallback_plan(topic, articles, keywords)
    title = plan.get("summary_title") or f"{topic} 관련 리포트"
    plan_keywords = plan.get("related_keywords") if isinstance(plan.get("related_keywords"), list) else keywords

    lines: list[str] = []
    lines.append("🎯 <b>텔레그램 요청 주제 분석</b>")
    lines.append(f"요청 주제: <b>{_h(topic)}</b>")
    lines.append(f"리포트 제목: <b>{_h(title)}</b>")
    lines.append("수집 기준: Google News RSS / 관련 기사·글로벌 속보 보강")

    lines.append("\n🔎 <b>관련 키워드</b>")
    lines.append(" · ".join(_h(k) for k in plan_keywords[:12]) if plan_keywords else "관련 키워드 추출 결과가 부족합니다.")

    lines.append("\n🔥 <b>관련 핫이슈 TOP 5</b>")
    for i, issue in enumerate((plan.get("hot_issues") or [])[:5], 1):
        if not isinstance(issue, dict):
            continue
        lines.append(f"\n<b>{i}. {_h(issue.get('title') or topic)}</b>")
        if issue.get("why"):
            lines.append(f"핵심: {_h(issue.get('why'))}")
        kws = issue.get("keywords") if isinstance(issue.get("keywords"), list) else []
        if kws:
            lines.append("키워드: " + ", ".join(_h(k) for k in kws[:5]))

    lines.append("\n🃏 <b>카드뉴스 후보</b>")
    for i, item in enumerate((plan.get("card_news_candidates") or [])[:3], 1):
        if not isinstance(item, dict):
            continue
        lines.append(f"\n<b>{i}. {_h(item.get('title') or topic)}</b>")
        if item.get("angle"):
            lines.append(f"소구점: {_h(item.get('angle'))}")
        if item.get("target"):
            lines.append(f"타깃: {_h(item.get('target'))}")

    lines.append("\n🎬 <b>카드뉴스 스크립트</b>")
    for slide in (plan.get("card_news_script") or [])[:8]:
        if not isinstance(slide, dict):
            continue
        lines.append(f"\n<b>{_h(slide.get('page') or '-') }장. {_h(slide.get('headline') or '')}</b>")
        if slide.get("body"):
            lines.append(_h(slide.get("body")))
        if slide.get("visual"):
            lines.append(f"이미지방향: {_h(slide.get('visual'))}")

    lines.append("\n✍️ <b>작성글 후보</b>")
    for i, item in enumerate((plan.get("article_candidates") or [])[:5], 1):
        if not isinstance(item, dict):
            continue
        lines.append(f"\n<b>{i}. {_h(item.get('seo_title') or topic)}</b>")
        if item.get("main_keyword"):
            lines.append(f"메인키워드: {_h(item.get('main_keyword'))}")
        subs = item.get("sub_keywords") if isinstance(item.get("sub_keywords"), list) else []
        if subs:
            lines.append("보조키워드: " + ", ".join(_h(k) for k in subs[:8]))
        if item.get("angle"):
            lines.append(f"글방향: {_h(item.get('angle'))}")

    lines.append("\n🧾 <b>근거자료</b>")
    lines.append(_news_links(articles, limit=max(5, min(10, _env_int("TELEGRAM_TOPIC_NEWS_LINKS", 8)))))
    return "\n".join(lines)


@app.route("/", methods=["GET", "POST"])
@app.route("/api/telegram_webhook", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "service": "gooddaynews-telegram-webhook",
            "version": VERSION,
            "route": "/api/telegram_webhook",
            "env": {
                "TELEGRAM_BOT_TOKEN": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()),
                "TELEGRAM_WEBHOOK_SECRET": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()),
                "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
            },
            "test": "Send /ping or /topic 원달러 환율 to Telegram.",
        })

    try:
        ss = _secret_info()
        if ss["strict"] and not ss["match"]:
            return jsonify({"ok": False, "error": "secret mismatch"}), 403

        update = request.get_json(silent=True) or {}
        update_type, msg = _extract_message(update)
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = (msg.get("text") or msg.get("caption") or "").strip()
        print("UPDATE_RECEIVED", {"update_type": update_type, "chat_id": chat_id, "text": text[:200], "version": VERSION})

        if not chat_id:
            return jsonify({"ok": True, "skipped": "no chat_id"})

        if text.lower().startswith("/ping"):
            status, body = _telegram_send(chat_id, (
                "✅ <b>Webhook received</b>\n"
                f"version: <code>{_h(VERSION)}</code>\n"
                f"chat_id: <code>{_h(chat_id)}</code>\n"
                f"secret_match: <code>{'yes' if ss['match'] else 'no'}</code>"
            ))
            return jsonify({"ok": True, "ping": True, "telegram_status": status, "telegram_body": body})

        topic = _extract_topic(text)
        if not topic:
            # Do not spam channels for every non-topic post unless explicitly enabled.
            if _env_bool("TELEGRAM_ECHO_UNKNOWN", "false"):
                _telegram_send(chat_id, "ℹ️ 주제 분석은 <code>/topic 원달러 환율</code> 형식으로 입력하세요.")
            return jsonify({"ok": True, "ignored": "no topic"})

        _telegram_send(chat_id, f"🧭 <b>주제 분석을 시작합니다.</b>\n요청 주제: <b>{_h(topic)}</b>\n잠시만 기다려주세요.")
        report = _build_report(topic)
        status, body = _telegram_send(chat_id, report)
        return jsonify({"ok": True, "topic": topic, "telegram_status": status, "telegram_body": body})
    except Exception as exc:
        print("WEBHOOK_EXCEPTION", repr(exc))
        print(traceback.format_exc())
        # Try to report errors back to the same Telegram chat when possible.
        try:
            update = request.get_json(silent=True) or {}
            _, msg = _extract_message(update)
            chat_id = (msg.get("chat") or {}).get("id")
            if chat_id:
                _telegram_send(chat_id, f"❌ <b>Webhook 오류</b>\n<code>{_h(str(exc)[:800])}</code>")
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1500:]}), 200
