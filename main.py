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

VERSION = "topic-report-flask-kr48-weather-personguard-2026-06-30-01"
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

KST = timezone(timedelta(hours=9))
DEFAULT_REGION = os.environ.get("DEFAULT_REGION", "KR").strip() or "KR"
DEFAULT_LOCALE = os.environ.get("DEFAULT_LOCALE", "ko-KR").strip() or "ko-KR"
DEFAULT_TIMEZONE = os.environ.get("DEFAULT_TIMEZONE", "Asia/Seoul").strip() or "Asia/Seoul"

STOPWORDS = {
    "속보", "단독", "종합", "사진", "영상", "뉴스", "관련", "오늘", "내일", "이번", "지난", "기자", "공식",
    "발표", "확인", "가능성", "영향", "전망", "시장", "경제", "글로벌", "한국", "미국", "중국", "정부",
    "서울", "전국", "날씨", "기상청", "오전", "오후", "오늘의",
    "after", "before", "with", "from", "that", "this", "will", "says", "said", "amid", "over", "into",
    "reuters", "bloomberg", "cnbc", "business", "markets", "breaking", "news", "global", "economy",
}

PERSON_CONTEXT_WORDS = {
    "대통령", "총리", "장관", "의원", "대표", "후보", "시장", "도지사", "교육감", "감독", "선수", "배우",
    "가수", "방송인", "교수", "회장", "사장", "대표이사", "의사", "변호사", "작가", "기자", "유튜버",
    "축구", "야구", "농구", "정치", "경제", "기업", "재판", "수사", "사건", "논란", "발언", "인터뷰",
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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _max_news_age_hours() -> int:
    # 모든 근거 기사 기본 제한. 사용자가 따로 지정하지 않으면 48시간.
    return max(1, _env_int("SUPPORTING_NEWS_MAX_AGE_HOURS", 48))


def _exclude_unknown_published() -> bool:
    # 발행시각을 확인할 수 없는 기사는 기본 제외.
    return _env_bool("EXCLUDE_UNKNOWN_PUBLISHED_AT", "true")


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


def _telegram_send_with_buttons(
    chat_id: Any,
    text: str,
    articles: list[dict[str, Any]],
    parse_mode: str | None = "HTML",
    button_limit: int | None = None,
) -> tuple[int, str]:
    """긴 URL을 본문에 노출하지 않고, 기사 링크를 버튼으로 분리해서 보냅니다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return 0, "TELEGRAM_BOT_TOKEN is missing"

    limit = button_limit or _env_int("TELEGRAM_LINK_BUTTON_LIMIT", 8)
    rows = []
    for i, article in enumerate(articles[:limit], 1):
        url = str(article.get("url") or "")
        if not url.startswith("http"):
            continue
        title = re.sub(r"\s+", " ", str(article.get("title") or f"기사 {i}")).strip()
        label = f"🔗 {i}. {title[:34]}"
        rows.append([{"text": label, "url": url}])

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:3900],
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if rows:
        payload["reply_markup"] = {"inline_keyboard": rows}

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    resp = requests.post(url, json=payload, timeout=25)
    if resp.status_code >= 400:
        print("TELEGRAM_BUTTON_SEND_FAILED", resp.status_code, resp.text[:1000])
    return resp.status_code, resp.text[:1000]


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


def _published_dt(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key, "") if isinstance(entry, dict) else getattr(entry, key, "")
        if value:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _is_recent_article(dt: datetime | None, max_age_hours: int | None = None) -> bool:
    max_age = max_age_hours or _max_news_age_hours()
    if dt is None:
        return not _exclude_unknown_published()
    return dt >= (_now_utc() - timedelta(hours=max_age))


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    title = re.sub(r"\s+-\s+[^-]{2,35}$", "", title).strip()
    return title[:140]


def _google_news_rss(query: str, *, geo: str = "KR", hl: str = "ko", limit: int = 8, lookback_hours: int | None = None) -> list[dict[str, Any]]:
    # Google News RSS 검색어에도 when:Nd를 붙이고, 수신 후 발행시각으로 한 번 더 48시간 필터링합니다.
    hours = lookback_hours or _max_news_age_hours()
    days = max(1, (hours + 23) // 24)
    q = quote_plus(f"{query} when:{days}d")
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={geo}&ceid={geo}:{hl}"
    feed = feedparser.parse(url)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in feed.entries[: max(limit * 3, limit)]:
        title = _clean_title(getattr(entry, "title", "") or entry.get("title", ""))
        link = getattr(entry, "link", "") or entry.get("link", "")
        source_obj = getattr(entry, "source", None) or entry.get("source", {})
        source = ""
        if isinstance(source_obj, dict):
            source = source_obj.get("title", "")
        else:
            source = getattr(source_obj, "title", "") if source_obj else ""

        dt = _published_dt(entry)
        if not _is_recent_article(dt, hours):
            continue

        key = re.sub(r"\s+", " ", title.lower())
        if not title or not link or key in seen:
            continue
        seen.add(key)
        items.append({
            "title": title,
            "url": link,
            "source": source or "Google News",
            "published_dt": dt,
            "published": dt.astimezone(KST).strftime("%m-%d %H:%M") if dt else "발행시각 미확인",
            "age_hours": round((_now_utc() - dt).total_seconds() / 3600, 1) if dt else None,
            "query": query,
        })
        if len(items) >= limit:
            break
    return items


def _is_weather_topic(topic: str) -> bool:
    text = str(topic or "").lower()
    return any(w in text for w in ["날씨", "기온", "비", "눈", "폭염", "한파", "미세먼지", "우산", "weather"])


def _fetch_weather() -> dict[str, Any] | None:
    """기본 지역은 서울. API 키 없이 Open-Meteo를 사용합니다."""
    if not _env_bool("WEATHER_ENABLED", "true"):
        return None

    lat = os.environ.get("WEATHER_DEFAULT_LAT", "37.5665").strip()
    lon = os.environ.get("WEATHER_DEFAULT_LON", "126.9780").strip()
    city = os.environ.get("WEATHER_DEFAULT_CITY", "서울").strip() or "서울"

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m"
            "&hourly=precipitation_probability,temperature_2m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&timezone=Asia%2FSeoul"
            "&forecast_days=1"
        )
        data = requests.get(url, timeout=12).json()
        current = data.get("current", {}) or {}
        daily = data.get("daily", {}) or {}
        return {
            "city": city,
            "temp": current.get("temperature_2m"),
            "feels": current.get("apparent_temperature"),
            "rain": current.get("rain"),
            "precip": current.get("precipitation"),
            "wind": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "max": (daily.get("temperature_2m_max") or [None])[0],
            "min": (daily.get("temperature_2m_min") or [None])[0],
            "pop": (daily.get("precipitation_probability_max") or [None])[0],
        }
    except Exception as exc:
        print("WEATHER_FETCH_ERROR", repr(exc))
        return None


def _weather_code_text(code: Any) -> str:
    try:
        c = int(code)
    except Exception:
        return "상태 확인 필요"
    if c == 0:
        return "맑음"
    if c in {1, 2, 3}:
        return "대체로 맑음/구름"
    if c in {45, 48}:
        return "안개"
    if c in {51, 53, 55, 56, 57}:
        return "이슬비"
    if c in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "비"
    if c in {71, 73, 75, 77, 85, 86}:
        return "눈"
    if c in {95, 96, 99}:
        return "뇌우"
    return "상태 확인 필요"


def _weather_section() -> str:
    weather = _fetch_weather()
    if not weather:
        return "🌤️ <b>오늘의 날씨</b>\n날씨 정보를 가져오지 못했습니다."

    condition = _weather_code_text(weather.get("weather_code"))
    pop = weather.get("pop")
    living = []
    if isinstance(pop, (int, float)) and pop >= 50:
        living.append("우산을 챙기는 편이 좋습니다.")
    if isinstance(weather.get("wind"), (int, float)) and weather["wind"] >= 8:
        living.append("바람이 강할 수 있어 외출 시 체감온도를 확인하세요.")
    if not living:
        living.append("외출 전 체감온도와 강수 가능성을 한 번 더 확인하세요.")

    return (
        f"🌤️ <b>오늘의 날씨</b>\n"
        f"기준지역: <b>{_h(weather.get('city'))}</b> / 한국시간\n"
        f"- 현재: {_h(condition)} / 기온 {_h(weather.get('temp'))}℃ / 체감 {_h(weather.get('feels'))}℃\n"
        f"- 오늘 최저·최고: {_h(weather.get('min'))}℃ ~ {_h(weather.get('max'))}℃\n"
        f"- 강수확률: {_h(pop)}% / 바람 {_h(weather.get('wind'))}km/h\n"
        f"- 생활 포인트: {_h(' '.join(living))}"
    )


def _looks_like_korean_person_name(text: str) -> bool:
    if not _env_bool("PERSON_KEYWORD_GUARD", "true"):
        return False
    value = re.sub(r"\s+", "", str(text or ""))
    if not re.fullmatch(r"[가-힣]{2,4}", value):
        return False
    common_non_people = {"금리", "환율", "유가", "날씨", "삼성", "현대", "정부", "국회", "서울", "부산", "코스피", "코스닥"}
    return value not in common_non_people


def _person_ambiguity_guard(topic: str, articles: list[dict[str, Any]]) -> dict[str, Any]:
    """동명이인 가능성을 경고합니다. 기사 제목의 직함/소속/분야 맥락이 흩어져 있으면 주의로 표시."""
    if not _looks_like_korean_person_name(topic):
        return {"is_person": False, "warning": "", "context_terms": []}

    contexts: list[str] = []
    titles_with_name = 0
    for article in articles[:12]:
        title = str(article.get("title") or "")
        if topic in title:
            titles_with_name += 1
        found = [w for w in PERSON_CONTEXT_WORDS if w in title]
        if found:
            contexts.extend(found[:3])

    unique_contexts = sorted(set(contexts))
    min_match = _env_int("PERSON_KEYWORD_MIN_CONTEXT_MATCH", 2)

    if titles_with_name < min_match:
        warning = f"‘{topic}’은 인물명 가능성이 있으나 최근 기사 제목에서 동일 인물로 볼 근거가 부족합니다."
    elif len(unique_contexts) >= 4:
        warning = f"‘{topic}’은 동명이인 가능성이 있어 직함·소속·사건명이 같은 기사만 근거로 사용해야 합니다."
    else:
        warning = f"‘{topic}’은 인물명 가능성이 있으므로 직함·소속·사건명 일치 여부를 확인했습니다."

    return {
        "is_person": True,
        "warning": warning,
        "context_terms": unique_contexts[:8],
        "titles_with_name": titles_with_name,
    }


def _fetch_articles(topic: str) -> list[dict[str, Any]]:
    geo = os.environ.get("GOOGLE_NEWS_GEO", DEFAULT_REGION).strip() or "KR"
    hl = os.environ.get("GOOGLE_NEWS_HL", "ko").strip() or "ko"
    limit = _env_int("TELEGRAM_TOPIC_NEWS_LINKS", 8)
    hours = _max_news_age_hours()

    queries = [
        topic,
        f"{topic} 최신",
        f"{topic} 경제 영향",
        f"{topic} 시장 전망",
    ]
    if _env_bool("TELEGRAM_TOPIC_INCLUDE_GLOBAL_BREAKING", "true"):
        queries.extend([
            f"{topic} Reuters Bloomberg markets economy",
            "Reuters breaking news global economy markets",
            "Bloomberg breaking news markets economy",
        ])

    seen: set[str] = set()
    articles: list[dict[str, Any]] = []
    per_query = max(3, min(6, limit))

    for query in queries:
        try:
            for item in _google_news_rss(query, geo=geo, hl=hl, limit=per_query, lookback_hours=hours):
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


def _gemini_plan(topic: str, articles: list[dict[str, Any]], keywords: list[str], person_guard: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    article_lines = []
    for i, a in enumerate(articles[:10], 1):
        article_lines.append(f"{i}. {a.get('title')} / {a.get('source')} / {a.get('published')} / {a.get('age_hours')}h")

    ambiguity_note = ""
    if person_guard.get("warning"):
        ambiguity_note = f"\n[인물명 검증 주의]\n{person_guard.get('warning')}\n맥락어: {', '.join(person_guard.get('context_terms') or [])}\n"

    prompt = f"""
너는 한국어 뉴스/애드센스/카드뉴스 기획자다.
기준 지역은 한국, 기준 시간은 한국시간이다.
근거 기사는 최근 {_max_news_age_hours()}시간 이내 기사만 사용한다.
발행시각이 불명확하거나 48시간 초과로 의심되는 기사는 근거로 쓰지 않는다.
한국어 인물명은 동명이인이 많으므로, 직함·소속·분야·사건명이 확인되지 않으면 단정하지 말고 '동명이인 가능성'을 표시한다.
과장하지 말고 기사 제목에서 확인 가능한 범위 안에서만 작성한다. 투자 조언처럼 확정하지 않는다.
제목만 봐도 어떤 정보가 들어 있는지 알 수 있게 쓴다.

[요청 주제]
{topic}

[키워드 후보]
{', '.join(keywords)}

{ambiguity_note}

[관련 기사]
{chr(10).join(article_lines) if article_lines else "최근 기준 확인된 기사 없음"}

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
                "why": "최근 48시간 이내 기사에서 확인되는 관련 이슈입니다.",
                "keywords": keywords[:4],
            })
    if not hot:
        hot.append({
            "title": f"{topic} 관련 최신 이슈 정리",
            "why": "최근 48시간 이내 확인 가능한 기사 근거가 부족합니다. 추가 보도 확인 후 사용이 안전합니다.",
            "keywords": keywords[:4],
        })
    return {
        "summary_title": f"{topic} 관련 핫이슈·카드뉴스·작성글 후보",
        "related_keywords": keywords[:10],
        "hot_issues": hot,
        "card_news_candidates": [
            {"title": f"{topic}, 지금 왜 주목받나", "angle": "배경 → 영향 → 체크포인트를 한눈에 보여주는 정보형 카드뉴스", "target": "뉴스를 빠르게 이해하고 싶은 독자"},
            {"title": f"{topic} 핵심 키워드 5가지", "angle": "복잡한 이슈를 키워드 중심으로 쪼개는 요약형 카드뉴스", "target": "블로그·인스타 유입 독자"},
            {"title": f"{topic}이 내 생활에 미치는 영향", "angle": "생활비·투자심리·소비자 관점의 실용형 카드뉴스", "target": "생활경제 관심 독자"},
        ],
        "card_news_script": [
            {"page": 1, "headline": f"{topic}, 왜 지금 주목받나", "body": "최근 관련 뉴스에서 이 주제가 다시 부각되고 있습니다.", "visual": "큰 제목과 키워드 구름"},
            {"page": 2, "headline": "핵심 키워드", "body": f"핵심은 {', '.join(keywords[:4]) or topic}입니다.", "visual": "키워드 4개 카드 배치"},
            {"page": 3, "headline": "생활·경제 영향", "body": "가격, 환율, 투자심리, 정책 기대에 영향을 줄 수 있습니다.", "visual": "영향 연결도"},
            {"page": 4, "headline": "관련 기사 흐름", "body": "최근 48시간 이내 기사 제목을 기준으로 흐름을 확인합니다.", "visual": "뉴스 타임라인"},
            {"page": 5, "headline": "확인할 체크포인트", "body": "공식 발표, 후속 기사, 수치 변화, 시장 반응을 함께 확인해야 합니다.", "visual": "체크리스트"},
            {"page": 6, "headline": "한 줄 정리", "body": "이슈 자체보다 원인과 파급효과를 함께 보는 것이 중요합니다.", "visual": "요약 문장 중심 마무리"},
        ],
        "article_candidates": [
            {"seo_title": f"{topic} 최신 이슈 정리, 왜 지금 주목해야 할까", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "배경·원인·영향을 정리하는 해설형 글"},
            {"seo_title": f"{topic} 관련 키워드와 영향 한눈에 보기", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "키워드 중심 검색 유입형 글"},
            {"seo_title": f"{topic}이 생활경제에 미치는 영향", "main_keyword": topic, "sub_keywords": keywords[:5], "angle": "생활경제 관점의 실용형 글"},
        ],
    }


def _news_links_text(articles: list[dict[str, Any]], limit: int = 8) -> str:
    if not articles:
        return f"최근 {_max_news_age_hours()}시간 이내 확인 가능한 기사 링크가 없습니다."
    lines = []
    for i, a in enumerate(articles[:limit], 1):
        title = _h(a.get("title", "기사 제목 없음"))
        source = _h(a.get("source", ""))
        published = _h(a.get("published", ""))
        age = a.get("age_hours")
        meta_parts = [x for x in [source, published, f"{age}h 전" if age is not None else ""] if x]
        meta = " · ".join(meta_parts)
        lines.append(f"  {i}) {title}" + (f" ({meta})" if meta else "") + f" / 링크{i}")
    return "\n".join(lines)


def _build_report(topic: str) -> tuple[str, list[dict[str, Any]]]:
    articles = _fetch_articles(topic)
    keywords = _extract_keywords(topic, articles)
    person_guard = _person_ambiguity_guard(topic, articles)
    plan = _gemini_plan(topic, articles, keywords, person_guard) or _fallback_plan(topic, articles, keywords)
    title = plan.get("summary_title") or f"{topic} 관련 리포트"
    plan_keywords = plan.get("related_keywords") if isinstance(plan.get("related_keywords"), list) else keywords

    lines: list[str] = []
    lines.append("🇰🇷 <b>기준: 한국 / 한국시간 / 최근 48시간 이내 기사</b>")

    if _is_weather_topic(topic) or _env_bool("ALWAYS_INCLUDE_WEATHER", "false"):
        lines.append("\n" + _weather_section())

    lines.append("\n🎯 <b>텔레그램 요청 주제 분석</b>")
    lines.append(f"요청 주제: <b>{_h(topic)}</b>")
    lines.append(f"리포트 제목: <b>{_h(title)}</b>")
    lines.append(f"수집 기준: Google News RSS / 한국 기준 / 최근 {_max_news_age_hours()}시간 이내 기사만 근거로 사용")

    if person_guard.get("warning"):
        lines.append("\n⚠️ <b>인물 키워드 검증</b>")
        lines.append(_h(person_guard.get("warning")))
        if person_guard.get("context_terms"):
            lines.append("확인된 맥락어: " + ", ".join(_h(x) for x in person_guard.get("context_terms", [])[:8]))

    if not articles:
        lines.append("\n⚠️ <b>근거 부족</b>")
        lines.append(f"최근 {_max_news_age_hours()}시간 이내 확인 가능한 기사 근거가 부족합니다. 오래된 기사는 근거에서 제외했습니다.")

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
    lines.append(_news_links_text(articles, limit=max(5, min(10, _env_int("TELEGRAM_TOPIC_NEWS_LINKS", 8)))))
    return "\n".join(lines), articles


@app.route("/", methods=["GET", "POST"])
@app.route("/api/telegram_webhook", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "service": "gooddaynews-telegram-webhook",
            "version": VERSION,
            "route": "/api/telegram_webhook",
            "defaults": {
                "region": DEFAULT_REGION,
                "locale": DEFAULT_LOCALE,
                "timezone": DEFAULT_TIMEZONE,
                "supporting_news_max_age_hours": _max_news_age_hours(),
                "exclude_unknown_published_at": _exclude_unknown_published(),
                "weather_enabled": _env_bool("WEATHER_ENABLED", "true"),
                "weather_default_city": os.environ.get("WEATHER_DEFAULT_CITY", "서울"),
                "person_keyword_guard": _env_bool("PERSON_KEYWORD_GUARD", "true"),
            },
            "env": {
                "TELEGRAM_BOT_TOKEN": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()),
                "TELEGRAM_WEBHOOK_SECRET": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()),
                "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
            },
            "test": "Send /ping, /topic 오늘 날씨, or /topic 원달러 환율 to Telegram.",
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
                f"secret_match: <code>{'yes' if ss['match'] else 'no'}</code>\n"
                f"region: <code>{_h(DEFAULT_REGION)}</code>\n"
                f"max_news_age: <code>{_max_news_age_hours()}h</code>"
            ))
            return jsonify({"ok": True, "ping": True, "telegram_status": status, "telegram_body": body})

        topic = _extract_topic(text)
        if not topic:
            if _env_bool("TELEGRAM_ECHO_UNKNOWN", "false"):
                _telegram_send(chat_id, "ℹ️ 주제 분석은 <code>/topic 원달러 환율</code> 형식으로 입력하세요.")
            return jsonify({"ok": True, "ignored": "no topic"})

        _telegram_send(chat_id, f"🧭 <b>주제 분석을 시작합니다.</b>\n요청 주제: <b>{_h(topic)}</b>\n기준: 한국 / 최근 48시간 이내 기사\n잠시만 기다려주세요.")
        report, articles = _build_report(topic)

        if _env_bool("TELEGRAM_URL_BUTTONS", "true"):
            status, body = _telegram_send_with_buttons(chat_id, report, articles)
        else:
            status, body = _telegram_send(chat_id, report)

        return jsonify({"ok": True, "topic": topic, "telegram_status": status, "telegram_body": body})

    except Exception as exc:
        print("WEBHOOK_EXCEPTION", repr(exc))
        print(traceback.format_exc())
        try:
            update = request.get_json(silent=True) or {}
            _, msg = _extract_message(update)
            chat_id = (msg.get("chat") or {}).get("id")
            if chat_id:
                _telegram_send(chat_id, f"❌ <b>Webhook 오류</b>\n<code>{_h(str(exc)[:800])}</code>")
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(exc), "trace": traceback.format_exc()[-1500:]}), 200
