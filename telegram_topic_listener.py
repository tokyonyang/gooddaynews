import os
import re
import json
import html as html_lib
from datetime import datetime, timezone, timedelta
from typing import Any

import requests
from dotenv import load_dotenv

from news_sources import fetch_related_news, fetch_global_breaking_news
from telegram_notify import split_long_text, clean_telegram_text

try:
    from content_generator import _extract_json
except Exception:
    _extract_json = None


TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return default


def _html(text: Any) -> str:
    return html_lib.escape(str(text or ""), quote=False)


def _html_attr(text: Any) -> str:
    return html_lib.escape(str(text or ""), quote=True)


def _parse_list(text: str) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    rows: list[str] = []
    seen = set()
    for part in re.split(r"[\n,;，、]+", text):
        item = re.sub(r"\s+", " ", part).strip(" -•\t")
        if item and item not in seen:
            seen.add(item)
            rows.append(item)
    return rows


def _api_url(token: str, method: str) -> str:
    return TELEGRAM_API_BASE.format(token=token, method=method)


def _post_telegram(token: str, method: str, payload: dict) -> dict:
    resp = requests.post(_api_url(token, method), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Telegram {method} failed: {resp.status_code} {resp.text[:500]}")
    return resp.json()


def _send_message(token: str, chat_id: str | int, text: str, parse_mode: str | None = "HTML") -> None:
    for chunk in split_long_text(clean_telegram_text(text)):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        _post_telegram(token, "sendMessage", payload)


def _get_updates(token: str, limit: int = 20) -> list[dict]:
    params = {
        "timeout": 0,
        "limit": max(1, min(int(limit or 20), 100)),
        "allowed_updates": ["message", "channel_post", "edited_message", "edited_channel_post"],
    }
    resp = requests.get(_api_url(token, "getUpdates"), params=params, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Telegram getUpdates failed: {resp.status_code} {resp.text[:500]}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates returned not ok: {data}")
    return data.get("result") or []


def _ack_updates(token: str, last_update_id: int) -> None:
    # getUpdates는 offset을 마지막 update_id보다 크게 호출하면 이전 업데이트를 확인 처리합니다.
    requests.get(
        _api_url(token, "getUpdates"),
        params={"offset": int(last_update_id) + 1, "timeout": 0, "limit": 1},
        timeout=30,
    )


def _message_from_update(update: dict) -> dict | None:
    for key in ("message", "channel_post", "edited_message", "edited_channel_post"):
        msg = update.get(key)
        if isinstance(msg, dict):
            return msg
    return None


def _allowed_chat(chat_id: str | int) -> bool:
    raw = os.environ.get("TELEGRAM_TOPIC_ALLOWED_CHAT_IDS") or os.environ.get("TELEGRAM_CHAT_ID", "")
    allowed = {x.strip() for x in re.split(r"[\s,;]+", str(raw)) if x.strip()}
    if not allowed:
        return True
    return str(chat_id) in allowed


def _extract_topic(text: str) -> str:
    """텔레그램 메시지에서 사용자가 요청한 주제만 추출합니다.

    지원 예시:
    - /topic 원달러 환율
    - /issue 엔비디아 실적
    - 주제: 삼성전자 HBM
    - 토픽 원유 급등
    - 핫이슈 트럼프 관세
    """
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
    for pattern in patterns:
        m = re.match(pattern, text, flags=re.IGNORECASE)
        if m:
            topic = m.group(1).strip()
            return topic[:120]

    # 설정을 켜면 명령어가 아닌 일반 문장도 주제로 처리합니다.
    if _env_true("TELEGRAM_TOPIC_ACCEPT_PLAIN", "false") and not text.startswith("/"):
        if len(text) <= 120 and not any(marker in text for marker in ["오늘의 핫이슈", "글로벌 속보", "카드뉴스 추천"]):
            return text
    return ""


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    title = re.sub(r"\s+-\s+[^-]{2,30}$", "", title).strip()
    return title[:120]


STOPWORDS = {
    "속보", "단독", "종합", "사진", "영상", "뉴스", "관련", "오늘", "내일", "이번", "지난", "기자", "공식",
    "발표", "확인", "가능성", "영향", "전망", "시장", "경제", "글로벌", "한국", "미국", "중국", "정부",
    "after", "before", "with", "from", "that", "this", "will", "says", "said", "amid", "over", "into",
    "reuters", "bloomberg", "cnbc", "business", "markets", "breaking", "news", "global", "economy",
}


def _extract_related_keywords(topic: str, articles: list[dict], max_keywords: int = 12) -> list[str]:
    score: dict[str, int] = {}
    seed_parts = re.split(r"[\s,/·]+", str(topic or ""))
    for p in seed_parts:
        p = p.strip()
        if len(p) >= 2:
            score[p] = score.get(p, 0) + 10

    for idx, article in enumerate(articles):
        title = _clean_title(article.get("title", ""))
        # 한글 명사/영문 주요 토큰 중심으로 가볍게 추출합니다.
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", title)
        for token in tokens:
            raw = token.strip()
            key = raw.lower()
            if key in STOPWORDS or raw in STOPWORDS:
                continue
            if raw.isdigit():
                continue
            if len(raw) > 22:
                continue
            score[raw] = score.get(raw, 0) + max(1, 8 - idx)

    ranked = sorted(score.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    result: list[str] = []
    seen_norm = set()
    for keyword, _ in ranked:
        norm = keyword.lower()
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        result.append(keyword)
        if len(result) >= max_keywords:
            break
    return result


def _news_links_html(articles: list[dict], limit: int = 5) -> str:
    if not articles:
        return "최근 기준 확인된 기사 링크가 없습니다."
    lines = []
    for idx, article in enumerate(articles[:limit], 1):
        title = _html(_clean_title(article.get("title", "") or "기사 제목 없음"))
        source = _html(article.get("source", ""))
        published = _html(article.get("published", ""))
        url = str(article.get("url") or "").strip()
        meta = " · ".join(x for x in [source, published] if x)
        link = f'<a href="{_html_attr(url)}">링크{idx}</a>' if url.startswith(("http://", "https://")) else f"링크{idx}"
        if meta:
            lines.append(f"  {idx}) {title} ({meta}) / {link}")
        else:
            lines.append(f"  {idx}) {title} / {link}")
    return "\n".join(lines)


def _gemini_topic_plan(topic: str, articles: list[dict], related_keywords: list[str]) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or _extract_json is None:
        return None

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    article_lines = []
    for idx, article in enumerate(articles[:10], 1):
        title = _clean_title(article.get("title", ""))
        source = article.get("source", "")
        published = article.get("published", "")
        article_lines.append(f"{idx}. {title} / {source} / {published}")

    prompt = f"""
너는 한국어 애드센스/카드뉴스 기획자다.
텔레그램으로 들어온 주제에 대해 관련 기사 제목을 바탕으로 리포트를 만든다.
과장하지 말고 기사에 근거해 작성한다. 투자 조언처럼 확정적으로 쓰지 않는다.

[요청 주제]
{topic}

[관련 키워드 후보]
{', '.join(related_keywords)}

[관련 기사]
{chr(10).join(article_lines)}

아래 JSON 형식만 반환해라.
{{
  "summary_title": "제목만 봐도 무엇을 다루는지 알 수 있는 한국어 제목",
  "related_keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5", "키워드6"],
  "hot_issues": [
    {{"title": "관련 핫이슈 제목", "why": "왜 중요한지 1문장", "keywords": ["키워드", "키워드"]}}
  ],
  "card_news_candidates": [
    {{"title": "카드뉴스 후보 제목", "angle": "카드뉴스 소구점", "target": "읽을 사람"}}
  ],
  "card_news_script": [
    {{"page": 1, "headline": "카드뉴스 1장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 2, "headline": "카드뉴스 2장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 3, "headline": "카드뉴스 3장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 4, "headline": "카드뉴스 4장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 5, "headline": "카드뉴스 5장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}},
    {{"page": 6, "headline": "카드뉴스 6장 헤드라인", "body": "짧은 본문", "visual": "이미지 방향"}}
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
        return data if isinstance(data, dict) else None
    except Exception as exc:
        print(f"[WARN] Gemini topic plan skipped: {exc}")
        return None


def _fallback_plan(topic: str, articles: list[dict], related_keywords: list[str]) -> dict:
    hot_issues = []
    for article in articles[:5]:
        title = _clean_title(article.get("title", ""))
        if not title:
            continue
        hot_issues.append({
            "title": title,
            "why": "최근 관련 기사에서 반복 확인되는 이슈로, 검색 유입과 카드뉴스 소재로 활용 가능합니다.",
            "keywords": related_keywords[:3],
        })

    if not hot_issues:
        hot_issues.append({
            "title": f"{topic} 관련 최신 이슈 정리",
            "why": "사용자가 직접 요청한 주제이므로 별도 분석 후보로 구성합니다.",
            "keywords": related_keywords[:3],
        })

    card_title = f"{topic}, 지금 왜 주목받나"
    return {
        "summary_title": f"{topic} 관련 핫이슈·카드뉴스·작성글 후보",
        "related_keywords": related_keywords[:8],
        "hot_issues": hot_issues[:5],
        "card_news_candidates": [
            {"title": card_title, "angle": "배경 → 영향 → 체크포인트를 한눈에 보여주는 정보형 카드뉴스", "target": "뉴스를 빠르게 이해하고 싶은 독자"},
            {"title": f"{topic} 핵심 키워드 5가지", "angle": "복잡한 이슈를 키워드 중심으로 쪼개는 요약형 카드뉴스", "target": "블로그·인스타 유입 독자"},
            {"title": f"{topic}이 내 지갑에 미치는 영향", "angle": "생활비·투자·소비자 관점의 실용형 카드뉴스", "target": "생활경제 관심 독자"},
        ],
        "card_news_script": [
            {"page": 1, "headline": card_title, "body": "최근 관련 뉴스에서 이 주제가 다시 주목받고 있습니다.", "visual": "큰 제목과 관련 키워드 구름"},
            {"page": 2, "headline": "핵심은 무엇인가", "body": f"핵심 키워드는 {', '.join(related_keywords[:4])}입니다.", "visual": "키워드 4개를 카드형으로 배치"},
            {"page": 3, "headline": "왜 지금 중요한가", "body": "최근 기사 흐름상 시장·정책·소비자 판단에 영향을 줄 수 있습니다.", "visual": "뉴스 타임라인"},
            {"page": 4, "headline": "영향받는 영역", "body": "가격, 투자심리, 정책 기대, 관련 업종을 나눠서 확인해야 합니다.", "visual": "4분할 영향도 그래픽"},
            {"page": 5, "headline": "확인할 체크포인트", "body": "공식 발표, 후속 기사, 수치 변화, 시장 반응을 함께 봐야 합니다.", "visual": "체크리스트 이미지"},
            {"page": 6, "headline": "한 줄 정리", "body": "단순 이슈 소비보다 원인과 영향을 함께 보는 것이 중요합니다.", "visual": "요약 문장 중심 마무리"},
        ],
        "article_candidates": [
            {"seo_title": f"{topic} 최신 이슈 정리, 왜 지금 주목해야 할까", "main_keyword": topic, "sub_keywords": related_keywords[:5], "angle": "배경·원인·영향을 정리하는 해설형 글"},
            {"seo_title": f"{topic} 관련 키워드와 영향 한눈에 보기", "main_keyword": topic, "sub_keywords": related_keywords[:5], "angle": "키워드 중심의 검색 유입형 글"},
            {"seo_title": f"{topic}이 경제와 생활에 미치는 영향", "main_keyword": topic, "sub_keywords": related_keywords[:5], "angle": "생활경제 관점의 실용형 글"},
        ],
    }


def _build_topic_report(topic: str) -> str:
    geo = os.environ.get("GOOGLE_TRENDS_GEO", "KR")
    lookback_hours = _safe_int_env("TELEGRAM_TOPIC_LOOKBACK_HOURS", _safe_int_env("LOOKBACK_HOURS", 48))
    links_per_topic = _safe_int_env("TELEGRAM_TOPIC_NEWS_LINKS", 8)
    global_count = _safe_int_env("TELEGRAM_TOPIC_GLOBAL_BREAKING_COUNT", 3)

    # 주제 자체 관련 기사
    related_articles = fetch_related_news(
        topic,
        limit=links_per_topic,
        geo=geo,
        category_hint="경제 금융 증권 정책 산업 글로벌 속보",
        lookback_hours=lookback_hours,
    )

    # 주제와 함께 볼 글로벌 속보도 3개만 보강합니다.
    global_breaking = []
    if _env_true("TELEGRAM_TOPIC_INCLUDE_GLOBAL_BREAKING", "true"):
        queries = [
            f"{topic} Reuters Bloomberg economy markets",
            f"{topic} breaking news economic impact",
        ]
        global_breaking = fetch_global_breaking_news(
            limit=global_count,
            geo=geo,
            lookback_hours=lookback_hours,
            queries=queries,
            use_direct_sites=_env_true("GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES", "true"),
            social_feeds=os.environ.get("GLOBAL_BREAKING_SOCIAL_FEEDS", ""),
            min_impact_score=2,
        )

    merged_articles = related_articles[:]
    seen_urls = {a.get("url") for a in merged_articles}
    for article in global_breaking:
        if article.get("url") not in seen_urls:
            merged_articles.append(article)
            seen_urls.add(article.get("url"))

    related_keywords = _extract_related_keywords(topic, merged_articles, max_keywords=12)
    plan = _gemini_topic_plan(topic, merged_articles, related_keywords) or _fallback_plan(topic, merged_articles, related_keywords)

    title = plan.get("summary_title") or f"{topic} 관련 핫이슈·카드뉴스·작성글 후보"
    plan_keywords = plan.get("related_keywords") if isinstance(plan.get("related_keywords"), list) else related_keywords

    lines: list[str] = []
    lines.append(f"🎯 <b>텔레그램 요청 주제 분석</b>")
    lines.append(f"요청 주제: <b>{_html(topic)}</b>")
    lines.append(f"리포트 제목: <b>{_html(title)}</b>")
    lines.append(f"수집 기준: 최근 <b>{lookback_hours}시간</b> / 관련 기사·글로벌 속보 보강")

    lines.append("\n🔎 <b>관련 키워드</b>")
    if plan_keywords:
        lines.append(" · ".join(_html(k) for k in plan_keywords[:12]))
    else:
        lines.append("관련 키워드 추출 결과가 부족합니다.")

    lines.append("\n🔥 <b>관련 핫이슈 TOP 5</b>")
    hot_issues = plan.get("hot_issues") if isinstance(plan.get("hot_issues"), list) else []
    if not hot_issues:
        lines.append("관련 핫이슈 후보가 부족합니다.")
    for idx, issue in enumerate(hot_issues[:5], 1):
        if not isinstance(issue, dict):
            continue
        lines.append(f"\n<b>{idx}. {_html(issue.get('title') or topic)}</b>")
        if issue.get("why"):
            lines.append(f"핵심: {_html(issue.get('why'))}")
        kws = issue.get("keywords") if isinstance(issue.get("keywords"), list) else []
        if kws:
            lines.append("키워드: " + ", ".join(_html(k) for k in kws[:5]))

    lines.append("\n🃏 <b>카드뉴스 후보</b>")
    card_candidates = plan.get("card_news_candidates") if isinstance(plan.get("card_news_candidates"), list) else []
    if not card_candidates:
        lines.append("카드뉴스 후보가 부족합니다.")
    for idx, item in enumerate(card_candidates[:3], 1):
        if not isinstance(item, dict):
            continue
        lines.append(f"\n<b>{idx}. {_html(item.get('title') or topic)}</b>")
        if item.get("angle"):
            lines.append(f"소구점: {_html(item.get('angle'))}")
        if item.get("target"):
            lines.append(f"타깃: {_html(item.get('target'))}")

    lines.append("\n🎬 <b>카드뉴스 스크립트</b>")
    script = plan.get("card_news_script") if isinstance(plan.get("card_news_script"), list) else []
    if not script:
        lines.append("스크립트 후보가 부족합니다.")
    for slide in script[:8]:
        if not isinstance(slide, dict):
            continue
        page = slide.get("page") or "-"
        lines.append(f"\n<b>{page}장. {_html(slide.get('headline') or '')}</b>")
        if slide.get("body"):
            lines.append(_html(slide.get("body")))
        if slide.get("visual"):
            lines.append(f"이미지방향: {_html(slide.get('visual'))}")

    lines.append("\n✍️ <b>작성글 후보</b>")
    article_candidates = plan.get("article_candidates") if isinstance(plan.get("article_candidates"), list) else []
    if not article_candidates:
        lines.append("작성글 후보가 부족합니다.")
    for idx, item in enumerate(article_candidates[:5], 1):
        if not isinstance(item, dict):
            continue
        lines.append(f"\n<b>{idx}. {_html(item.get('seo_title') or topic)}</b>")
        if item.get("main_keyword"):
            lines.append(f"메인키워드: {_html(item.get('main_keyword'))}")
        sub = item.get("sub_keywords") if isinstance(item.get("sub_keywords"), list) else []
        if sub:
            lines.append("보조키워드: " + ", ".join(_html(k) for k in sub[:8]))
        if item.get("angle"):
            lines.append(f"글방향: {_html(item.get('angle'))}")

    lines.append("\n🧾 <b>근거자료</b>")
    lines.append(_news_links_html(merged_articles, limit=max(5, min(10, links_per_topic))))

    lines.append("\n📌 <b>사용법</b>")
    lines.append("텔레그램에 <code>/topic 원달러 환율</code> 또는 <code>주제: 엔비디아 실적</code>처럼 보내면 같은 형식으로 다시 정리합니다.")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("[INFO] TELEGRAM_BOT_TOKEN is not set. Skip.")
        return

    max_updates = _safe_int_env("TELEGRAM_TOPIC_MAX_UPDATES", 20)
    updates = _get_updates(token, limit=max_updates)
    if not updates:
        print("[INFO] No Telegram updates.")
        return

    last_update_id = max(int(u.get("update_id", 0)) for u in updates)
    processed = 0

    try:
        for update in updates:
            msg = _message_from_update(update)
            if not msg:
                continue
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None or not _allowed_chat(chat_id):
                continue
            text = msg.get("text") or msg.get("caption") or ""
            topic = _extract_topic(text)
            if not topic:
                continue

            processed += 1
            _send_message(token, chat_id, f"🧭 <b>주제 분석을 시작합니다.</b>\n요청 주제: <b>{_html(topic)}</b>\n잠시만 기다려주세요.", parse_mode="HTML")
            try:
                report = _build_topic_report(topic)
                _send_message(token, chat_id, report, parse_mode="HTML")
            except Exception as exc:
                err = re.sub(r"\s+", " ", str(exc)).strip()[:600]
                _send_message(token, chat_id, f"❌ 주제 분석 중 오류가 발생했습니다.\n<code>{_html(err)}</code>", parse_mode="HTML")
    finally:
        _ack_updates(token, last_update_id)

    print(f"[INFO] Telegram topic listener processed {processed} topic request(s).")


if __name__ == "__main__":
    main()
