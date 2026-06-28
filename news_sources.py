import html
import os
import math
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser

from seo_utils import clean_text

try:
    from naver_sources import fetch_naver_news
except Exception:
    fetch_naver_news = None


GOOGLE_NEWS_SEARCH_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"


def _source_name(entry) -> str:
    source = getattr(entry, "source", None)
    if isinstance(source, dict):
        return clean_text(source.get("title", ""))
    title = getattr(source, "title", "") if source else ""
    return clean_text(title)


def _parse_entry_datetime(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    raw = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
    raw = clean_text(raw)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _published_display(entry_dt: datetime | None, entry) -> str:
    if entry_dt is not None:
        # 최근 24시간 운영에서 보기 쉽게 월일/시분까지 표시합니다. UTC 기준이므로 KST로 변환합니다.
        kst = entry_dt.astimezone(timezone(timedelta(hours=9)))
        return kst.strftime("%m-%d %H:%M")
    raw = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
    raw = clean_text(raw)
    return raw[:16] if raw else ""


def _age_hours(entry_dt: datetime | None) -> float | None:
    if entry_dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600)



def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _dedupe_news(articles: list[dict], limit: int) -> list[dict]:
    rows = []
    seen = set()
    for article in articles:
        title = clean_text(article.get("title", ""))
        url = clean_text(article.get("url", ""))
        key = re.sub(r"\s+", " ", title.lower()) or url
        if not title or not url or key in seen:
            continue
        seen.add(key)
        rows.append(article)
        if len(rows) >= limit:
            break
    return rows

def _fetch_google_news(
    keyword: str,
    limit: int = 5,
    geo: str = "KR",
    category_hint: str = "",
    lookback_hours: int = 24,
) -> list[dict]:
    keyword = clean_text(keyword)
    if not keyword:
        return []

    hours = max(1, int(lookback_hours or 24))
    days = max(1, math.ceil(hours / 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    hint = clean_text(category_hint)
    search_text = f"{keyword} {hint} when:{days}d" if hint else f"{keyword} when:{days}d"
    query = quote_plus(search_text)
    url = GOOGLE_NEWS_SEARCH_RSS.format(query=query)

    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        print(f"[WARN] Google News RSS fetch failed for {keyword}: {exc}")
        return []

    rows: list[dict] = []
    seen = set()
    for entry in getattr(feed, "entries", [])[: max(limit * 4, limit)]:
        entry_dt = _parse_entry_datetime(entry)
        if entry_dt is not None and entry_dt < cutoff:
            continue

        title = clean_text(html.unescape(getattr(entry, "title", "")))
        link = clean_text(getattr(entry, "link", ""))
        source = _source_name(entry)
        published = _published_display(entry_dt, entry)
        age = _age_hours(entry_dt)

        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()

        dedupe_key = re.sub(r"\s+", " ", title.lower())
        if not title or not link or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        rows.append({
            "title": title,
            "url": link,
            "source": source,
            "published": published,
            "published_at": entry_dt.isoformat() if entry_dt else "",
            "age_hours": round(age, 2) if age is not None else "",
            "provider": "google_news",
        })
        if len(rows) >= limit:
            break

    return rows


# -----------------------------------------------------------------------------
# 글로벌 속보 TOP 3 수집
# -----------------------------------------------------------------------------
GLOBAL_BREAKING_DEFAULT_QUERIES = [
    "Reuters breaking news global economy markets",
    "Bloomberg breaking news global economy markets",
    "Reuters markets oil dollar rates stocks breaking",
    "Bloomberg markets Fed rates dollar oil breaking",
    "war sanctions oil markets breaking news",
    "WHO disease outbreak economy travel markets breaking news",
    "central bank interest rates inflation bond yields breaking news",
    "tariffs sanctions supply chain chips oil breaking news",
]

# Google News RSS가 느리거나 비어 있을 때 보조 확인할 실제 뉴스/기관 사이트의 공개 RSS 후보입니다.
# 일부 사이트는 지역/차단 정책에 따라 실패할 수 있으므로 실패해도 전체 작업은 계속 진행합니다.
GLOBAL_BREAKING_DIRECT_FEEDS = [
    {"name": "AP Business", "url": "https://apnews.com/hub/business?output=rss", "type": "news_site_rss"},
    {"name": "AP World", "url": "https://apnews.com/hub/world-news?output=rss", "type": "news_site_rss"},
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "type": "news_site_rss"},
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "type": "news_site_rss"},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "type": "news_site_rss"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "type": "news_site_rss"},
    {"name": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "type": "official_feed"},
    {"name": "WHO News", "url": "https://www.who.int/rss-feeds/news-english.xml", "type": "official_feed"},
]

ECONOMIC_IMPACT_RULES = [
    ("전쟁·지정학", "유가·금값·방산·해운·환율 변동 가능성", [
        "war", "attack", "missile", "sanction", "sanctions", "invasion", "strike", "ceasefire", "conflict",
        "ukraine", "russia", "israel", "iran", "taiwan", "china military", "red sea", "hormuz",
        "전쟁", "공습", "미사일", "제재", "확전", "휴전", "침공", "지정학", "호르무즈",
    ]),
    ("질병·감염병", "여행·항공·소비·공급망 위축 가능성", [
        "disease", "virus", "outbreak", "pandemic", "who", "bird flu", "avian flu", "covid",
        "질병", "감염병", "바이러스", "팬데믹", "조류독감", "코로나",
    ]),
    ("환율·달러", "원·달러 환율, 수입물가, 해외직구 원가, 외국인 수급 영향", [
        "dollar", "currency", "forex", "yen", "yuan", "won", "euro", "fx", "dxy",
        "환율", "달러", "원달러", "원·달러", "엔화", "위안", "외환",
    ]),
    ("원자재·유가", "물가·운송비·에너지·식품 원가 변동 가능성", [
        "oil", "crude", "brent", "wti", "opec", "gold", "copper", "wheat", "corn", "grain", "commodity", "commodities",
        "유가", "원유", "브렌트", "금값", "구리", "곡물", "원자재", "opec",
    ]),
    ("금리·채권", "대출금리·채권금리·주식 밸류에이션·부동산 심리 영향", [
        "rate", "rates", "fed", "fomc", "powell", "treasury", "yield", "bond", "inflation", "cpi", "pce", "ecb",
        "금리", "연준", "파월", "국채", "채권", "수익률", "인플레이션", "물가", "cpi", "pce",
    ]),
    ("무역·관세", "수출입 가격·공급망·반도체/자동차 업종 영향", [
        "tariff", "tariffs", "trade", "export", "import", "supply chain", "chips", "semiconductor", "restriction", "ban",
        "관세", "무역", "수출", "수입", "공급망", "반도체", "수출통제", "제한",
    ]),
    ("금융시장", "글로벌 증시·위험자산·외국인 수급 변동 가능성", [
        "markets", "stocks", "shares", "nasdaq", "s&p", "dow", "futures", "selloff", "rally", "bank", "banks",
        "증시", "주식", "나스닥", "선물", "은행", "금융시장", "급등", "급락",
    ]),
    ("기업·빅테크", "주요 기업 실적·AI/반도체·플랫폼 규제 관련 업종 영향", [
        "nvidia", "apple", "microsoft", "meta", "tesla", "google", "alphabet", "amazon", "openai", "ai", "earnings", "antitrust",
        "엔비디아", "애플", "마이크로소프트", "테슬라", "구글", "아마존", "실적", "ai", "반독점",
    ]),
    ("영향력 인물 발언/SNS", "정책 기대·기업 주가·시장 심리의 단기 변동성 확대 가능성", [
        "trump", "musk", "powell", "xi", "biden", "zelensky", "putin", "yellen", "lagarde", "posted", "tweet", "truth social", "x post",
        "트럼프", "머스크", "파월", "시진핑", "젤렌스키", "푸틴", "옐런", "라가르드", "게시", "SNS", "소셜",
    ]),
]


def _parse_feed_specs(text: str) -> list[dict]:
    """`이름|URL` 또는 URL만 들어온 사용자 지정 RSS/Atom/SNS feed 목록을 파싱합니다."""
    text = str(text or "").strip()
    if not text:
        return []
    specs = []
    for chunk in re.split(r"[\n,;]+", text):
        item = chunk.strip()
        if not item:
            continue
        if "|" in item:
            name, url = item.split("|", 1)
            name, url = clean_text(name), clean_text(url)
        else:
            url = clean_text(item)
            name = re.sub(r"^https?://", "", url).split("/")[0] or "Custom Feed"
        if url.startswith(("http://", "https://")):
            specs.append({"name": name or "Custom Feed", "url": url, "type": "custom_social_or_feed"})
    return specs


def _economic_impact(article: dict) -> tuple[int, str, str]:
    text = f"{article.get('title', '')} {article.get('source', '')} {article.get('query_context', '')}".lower()
    best_score = 0
    best_label = "글로벌경제"
    best_reason = "글로벌 경제·시장 영향 확인 필요"
    for label, reason, keywords in ECONOMIC_IMPACT_RULES:
        score = 0
        for keyword in keywords:
            needle = str(keyword or "").lower()
            if needle and needle in text:
                score += max(1, min(len(needle), 12))
        if score > best_score:
            best_score = score
            best_label = label
            best_reason = reason
    urgent_terms = ["breaking", "urgent", "exclusive", "alert", "속보", "긴급", "급등", "급락", "폭등", "폭락"]
    best_score += sum(5 for term in urgent_terms if term in text)
    if any(term in text for term in ["reuters", "bloomberg", "markets", "economy", "business", "finance", "global"]):
        best_score += 2
    return best_score, best_label, best_reason


def _sort_dt_key(article: dict) -> datetime:
    raw = clean_text(article.get("published_at", ""))
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fetch_rss_feed(url: str, source_name: str, limit: int, lookback_hours: int, provider: str) -> list[dict]:
    hours = max(1, int(lookback_hours or 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        feed = feedparser.parse(
            url,
            request_headers={
                "User-Agent": "Mozilla/5.0 gooddaynews-telegram-bot/1.0 (+https://gooddaynews.store)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )
    except Exception as exc:
        print(f"[WARN] RSS feed fetch failed for {source_name}: {exc}")
        return []

    rows: list[dict] = []
    for entry in getattr(feed, "entries", [])[: max(limit * 4, limit)]:
        entry_dt = _parse_entry_datetime(entry)
        if entry_dt is not None and entry_dt < cutoff:
            continue
        title = clean_text(html.unescape(getattr(entry, "title", "")))
        link = clean_text(getattr(entry, "link", ""))
        source = _source_name(entry) or source_name
        published = _published_display(entry_dt, entry)
        age = _age_hours(entry_dt)
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        if not title or not link:
            continue
        rows.append({
            "title": title,
            "url": link,
            "source": source,
            "published": published,
            "published_at": entry_dt.isoformat() if entry_dt else "",
            "age_hours": round(age, 2) if age is not None else "",
            "provider": provider,
            "query_context": source_name,
        })
        if len(rows) >= limit:
            break
    return rows


def fetch_global_breaking_news(
    limit: int = 3,
    geo: str = "KR",
    lookback_hours: int = 24,
    queries: list[str] | None = None,
    use_direct_sites: bool = True,
    social_feeds: str = "",
    min_impact_score: int = 3,
) -> list[dict]:
    """경제 영향 가능성이 있는 글로벌 속보를 최신 발행순으로 최대 limit개 반환합니다.

    1차: Google News RSS 검색(Reuters/Bloomberg/시장 키워드)
    2차: 실제 뉴스/기관 사이트의 공개 RSS 후보
    3차: 사용자가 지정한 SNS/RSS/Atom feed URL

    최종 정렬은 `경제영향 점수 기준 필터 통과 → 발행시각 최신순`입니다.
    """
    count = max(1, int(limit or 3))
    hours = max(1, int(lookback_hours or 24))
    query_list = [clean_text(q) for q in (queries or GLOBAL_BREAKING_DEFAULT_QUERIES) if clean_text(q)]

    candidates: list[dict] = []
    per_query_limit = max(4, count * 4)
    for query in query_list:
        rows = _fetch_google_news(
            query,
            limit=per_query_limit,
            geo=geo,
            category_hint="Reuters Bloomberg breaking economy markets oil dollar rates war disease central bank",
            lookback_hours=hours,
        )
        for row in rows:
            row["query_context"] = query
            row["provider"] = row.get("provider") or "google_news"
        candidates.extend(rows)

    if use_direct_sites:
        for spec in GLOBAL_BREAKING_DIRECT_FEEDS:
            candidates.extend(_fetch_rss_feed(
                spec["url"],
                spec["name"],
                limit=max(8, count * 4),
                lookback_hours=hours,
                provider=spec.get("type", "news_site_rss"),
            ))

    for spec in _parse_feed_specs(social_feeds):
        candidates.extend(_fetch_rss_feed(
            spec["url"],
            spec["name"],
            limit=max(5, count * 3),
            lookback_hours=hours,
            provider=spec.get("type", "custom_social_or_feed"),
        ))

    deduped: list[dict] = []
    seen = set()
    for article in candidates:
        title = clean_text(article.get("title", ""))
        url = clean_text(article.get("url", ""))
        key = re.sub(r"\s+", " ", title.lower()) or url
        if not title or not url or key in seen:
            continue
        seen.add(key)
        score, label, reason = _economic_impact(article)
        article["impact_score"] = score
        article["impact_label"] = label
        article["impact_reason"] = reason
        article["is_social_feed"] = article.get("provider") == "custom_social_or_feed"
        deduped.append(article)

    impacted = [a for a in deduped if int(a.get("impact_score", 0) or 0) >= int(min_impact_score or 0)]
    if not impacted:
        impacted = sorted(deduped, key=lambda a: (int(a.get("impact_score", 0) or 0), _sort_dt_key(a)), reverse=True)

    impacted.sort(key=lambda a: (_sort_dt_key(a), int(a.get("impact_score", 0) or 0)), reverse=True)
    return impacted[:count]


def fetch_related_news(
    keyword: str,
    limit: int = 5,
    geo: str = "KR",
    category_hint: str = "",
    lookback_hours: int = 24,
) -> list[dict]:
    """관련 신문 기사 링크를 가져옵니다.

    기본값은 네이버 뉴스 검색 API 우선입니다. 네이버 키가 없거나 결과가 부족하면
    Google News RSS로 부족분을 보완합니다.
    """
    keyword = clean_text(keyword)
    if not keyword:
        return []

    provider = os.environ.get("NEWS_PROVIDER", "naver_first").strip().lower()
    rows: list[dict] = []

    if provider in {"naver", "naver_first", "mixed"} and fetch_naver_news is not None:
        try:
            rows.extend(fetch_naver_news(keyword, limit=limit, lookback_hours=lookback_hours))
        except Exception as exc:
            print(f"[WARN] Naver News fetch skipped for {keyword}: {exc}")

    if provider in {"google", "google_first"}:
        rows.extend(_fetch_google_news(keyword, limit=limit, geo=geo, category_hint=category_hint, lookback_hours=lookback_hours))
    elif len(rows) < limit and provider in {"naver_first", "mixed"}:
        rows.extend(_fetch_google_news(keyword, limit=limit - len(rows), geo=geo, category_hint=category_hint, lookback_hours=lookback_hours))

    return _dedupe_news(rows, limit)
