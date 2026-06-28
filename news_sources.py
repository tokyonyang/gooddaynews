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
