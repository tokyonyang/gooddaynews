from __future__ import annotations

import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import requests
from dotenv import load_dotenv

from news_sources import fetch_related_news, fetch_global_breaking_news
from telegram_notify import send_telegram_with_buttons, html_escape

load_dotenv()

KST = timezone(timedelta(hours=9))


def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return default


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


def fetch_today_weather() -> dict[str, Any] | None:
    if not _env_bool("WEATHER_ENABLED", "true"):
        return None

    city = os.environ.get("WEATHER_DEFAULT_CITY", "서울").strip() or "서울"
    lat = os.environ.get("WEATHER_DEFAULT_LAT", "37.5665").strip()
    lon = os.environ.get("WEATHER_DEFAULT_LON", "126.9780").strip()

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&timezone=Asia%2FSeoul&forecast_days=1"
        )
        data = requests.get(url, timeout=12).json()
        current = data.get("current", {}) or {}
        daily = data.get("daily", {}) or {}
        return {
            "city": city,
            "condition": _weather_code_text(current.get("weather_code")),
            "temp": current.get("temperature_2m"),
            "feels": current.get("apparent_temperature"),
            "wind": current.get("wind_speed_10m"),
            "min": (daily.get("temperature_2m_min") or [None])[0],
            "max": (daily.get("temperature_2m_max") or [None])[0],
            "pop": (daily.get("precipitation_probability_max") or [None])[0],
        }
    except Exception as exc:
        print("[WARN] weather fetch failed:", repr(exc))
        return None


def weather_section() -> str:
    w = fetch_today_weather()
    if not w:
        return "🌤️ <b>오늘의 날씨</b>\n- 날씨 정보를 가져오지 못했습니다."

    living = []
    if isinstance(w.get("pop"), (int, float)) and w["pop"] >= 50:
        living.append("우산을 챙기는 편이 좋습니다.")
    if isinstance(w.get("wind"), (int, float)) and w["wind"] >= 8:
        living.append("바람이 강할 수 있어 체감온도를 확인하세요.")
    if not living:
        living.append("외출 전 체감온도와 강수 가능성을 한 번 더 확인하세요.")

    return (
        "🌤️ <b>오늘의 날씨</b>\n"
        f"- 기준지역: <b>{html_escape(w.get('city'))}</b> / 한국시간\n"
        f"- 현재: {html_escape(w.get('condition'))} / 기온 {html_escape(w.get('temp'))}℃ / 체감 {html_escape(w.get('feels'))}℃\n"
        f"- 오늘 최저·최고: {html_escape(w.get('min'))}℃ ~ {html_escape(w.get('max'))}℃ / 강수확률 {html_escape(w.get('pop'))}%\n"
        f"- 생활 포인트: {html_escape(' '.join(living))}"
    )


def _topics() -> list[str]:
    raw = os.environ.get("MORNING_BRIEFING_TOPICS", "").strip()
    if raw:
        rows = [x.strip() for x in re.split(r"[\n,;]+", raw) if x.strip()]
        if rows:
            return rows[: _env_int("MORNING_TOPIC_LIMIT", 10)]
    return [
        "원달러 환율",
        "코스피 외국인 수급",
        "미국 고용보고서",
        "연준 금리",
        "AI 반도체",
        "국제유가",
        "원자재 가격",
        "부동산 정책",
        "국내 경제 정책",
        "글로벌 증시",
    ][: _env_int("MORNING_TOPIC_LIMIT", 10)]


def _short_summary(topic: str, articles: list[dict]) -> str:
    if not articles:
        return f"{topic} 관련 최근 48시간 이내 확인 가능한 기사 근거가 부족합니다."
    title = articles[0].get("title") or ""
    return f"{topic} 관련 최신 보도에서 '{title[:50]}' 흐름이 확인됩니다."


def build_morning_briefing() -> tuple[str, list[dict]]:
    now = datetime.now(KST)
    lookback = min(_env_int("MORNING_LOOKBACK_HOURS", 24), _env_int("SUPPORTING_NEWS_MAX_AGE_HOURS", 48))
    links_per_topic = _env_int("MORNING_LINKS_PER_TOPIC", 2)

    all_articles: list[dict] = []
    topic_rows = []

    for topic in _topics():
        articles = fetch_related_news(topic, limit=links_per_topic, geo="KR", category_hint="경제 금융 증시 정책", lookback_hours=lookback)
        all_articles.extend(articles)
        topic_rows.append((topic, articles, _short_summary(topic, articles)))

    # 글로벌 속보 보강
    global_items = []
    if _env_bool("MORNING_INCLUDE_GLOBAL_BREAKING", "true"):
        global_items = fetch_global_breaking_news(
            limit=_env_int("MORNING_GLOBAL_BREAKING_COUNT", 3),
            geo="KR",
            lookback_hours=lookback,
            use_direct_sites=_env_bool("GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES", "true"),
            social_feeds=os.environ.get("GLOBAL_BREAKING_SOCIAL_FEEDS", ""),
        )
        all_articles.extend(global_items)

    lines = [
        f"🌅 <b>{now.strftime('%-m월 %-d일')} 모닝 브리핑</b>",
        "기준: <b>한국 / 한국시간 / 최근 48시간 이내 기사</b>",
        "",
        "좋은 아침입니다. 오늘 확인할 핵심 이슈를 짧게 정리했습니다.",
        "",
        weather_section(),
        "",
        "🔥 <b>오늘의 핫이슈 키워드</b>",
    ]

    for topic, articles, summary in topic_rows[:10]:
        lines.append(f"#{html_escape(topic.replace(' ', ''))} - {html_escape(summary)}")

    lines.append("\n🇰🇷 <b>국내·경제 주요 체크포인트</b>")
    for i, (topic, articles, summary) in enumerate(topic_rows[:5], 1):
        lines.append(f"{i}) <b>{html_escape(topic)}</b>\n{html_escape(summary)}")

    if global_items:
        lines.append("\n🌎 <b>글로벌 속보 체크</b>")
        for i, article in enumerate(global_items, 1):
            title = html_escape(article.get("title") or "글로벌 속보")
            source = html_escape(article.get("source") or "")
            published = html_escape(article.get("published") or "")
            label = html_escape(article.get("impact_label") or "글로벌경제")
            lines.append(f"{i}) [{label}] {title} ({source} · {published})")

    lines.append("\n💹 <b>투자·생활 포인트</b>")
    lines.append("✅ 환율·금리·외국인 수급은 함께 확인하세요.")
    lines.append("✅ AI·반도체는 실적 기대와 과열 논란을 동시에 봐야 합니다.")
    lines.append("✅ 원자재·유가는 물가와 운송비에 연결될 수 있습니다.")
    lines.append("✅ 최근 48시간 이내 근거가 부족한 이슈는 카드뉴스화 전 추가 확인이 필요합니다.")

    if topic_rows:
        one_line = " / ".join(topic for topic, _, _ in topic_rows[:4])
    else:
        one_line = "환율·금리·증시·글로벌 속보"
    lines.append(f"\n🌤️ <b>오늘 한 줄 요약</b>\n오늘은 <b>{html_escape(one_line)}</b> 흐름을 중심으로 확인하세요.")

    lines.append("\n🔗 <b>참고한 주요 기사</b>")
    if all_articles:
        seen = set()
        count = 0
        for article in all_articles:
            url = article.get("url") or ""
            title = article.get("title") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            count += 1
            lines.append(f"- 링크{count}: {html_escape(title)}")
            if count >= _env_int("MORNING_LINK_BUTTON_LIMIT", 8):
                break
    else:
        lines.append("- 최근 48시간 이내 확인 가능한 기사 근거가 부족합니다.")

    return "\n".join(lines), all_articles


def main():
    text, articles = build_morning_briefing()
    send_telegram_with_buttons(
        text,
        articles,
        parse_mode="HTML",
        button_limit=_env_int("MORNING_LINK_BUTTON_LIMIT", 8),
    )


if __name__ == "__main__":
    main()
