import html
import os
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests
import pandas as pd

from seo_utils import clean_text, is_valid_korean_keyword


NAVER_NEWS_API = "https://openapi.naver.com/v1/search/news.json"
NAVER_DATALAB_API = "https://openapi.naver.com/v1/datalab/search"


def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def naver_enabled() -> bool:
    return bool(os.environ.get("NAVER_CLIENT_ID") and os.environ.get("NAVER_CLIENT_SECRET"))


def _headers() -> dict:
    return {
        "X-Naver-Client-Id": os.environ.get("NAVER_CLIENT_ID", ""),
        "X-Naver-Client-Secret": os.environ.get("NAVER_CLIENT_SECRET", ""),
    }


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    return clean_text(html.unescape(text))


def _parse_pubdate(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _published_display(dt: datetime | None) -> str:
    if dt is None:
        return ""
    kst = dt.astimezone(timezone(timedelta(hours=9)))
    return kst.strftime("%m-%d %H:%M")


def _age_hours(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)


def _domain_name(url: str) -> str:
    try:
        host = urlparse(url).netloc.replace("www.", "")
        return host or "네이버뉴스"
    except Exception:
        return "네이버뉴스"


def fetch_naver_news(keyword: str, limit: int = 5, lookback_hours: int = 24, display: int | None = None) -> list[dict]:
    """네이버 뉴스 검색 API에서 최근 기사 링크를 가져옵니다.

    네이버 API는 개별 기사 조회수는 제공하지 않습니다. 여기서는 최근 기사 수와 발행시각을
    한국형 이슈 검증 신호로 사용합니다.
    """
    keyword = clean_text(keyword)
    if not keyword or not naver_enabled():
        return []

    hours = max(1, int(lookback_hours or 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    display = max(limit * 4, display or min(100, max(20, limit * 6)))

    params = {
        "query": keyword,
        "display": min(100, display),
        "start": 1,
        "sort": "date",
    }

    try:
        resp = requests.get(NAVER_NEWS_API, headers=_headers(), params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"[WARN] Naver News API fetch failed for {keyword}: {exc}")
        return []

    rows: list[dict] = []
    seen = set()
    for item in data.get("items", []):
        pub_dt = _parse_pubdate(item.get("pubDate", ""))
        if pub_dt is not None and pub_dt < cutoff:
            continue

        title = _strip_tags(item.get("title", ""))
        description = _strip_tags(item.get("description", ""))
        original = clean_text(item.get("originallink", ""))
        link = clean_text(item.get("link", ""))
        url = original or link
        if not title or not url:
            continue

        dedupe_key = re.sub(r"\s+", " ", title.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        age = _age_hours(pub_dt)
        rows.append({
            "title": title,
            "url": url,
            "source": _domain_name(original or link),
            "published": _published_display(pub_dt),
            "published_at": pub_dt.isoformat() if pub_dt else "",
            "age_hours": round(age, 2) if age is not None else "",
            "description": description,
            "provider": "naver_news",
        })
        if len(rows) >= limit:
            break

    return rows


def fetch_naver_news_signal(keyword: str, lookback_hours: int = 24, display: int = 30) -> dict:
    """최근 네이버 뉴스량을 점수화하기 위한 보조 신호입니다."""
    news = fetch_naver_news(keyword, limit=display, lookback_hours=lookback_hours, display=display)
    return {
        "naver_news_count": len(news),
        "naver_news_latest_at": news[0].get("published_at", "") if news else "",
    }


def fetch_naver_datalab_score(keyword: str, lookback_hours: int = 24) -> float:
    """네이버 데이터랩 통합검색어 트렌드 상대지수 평균값을 반환합니다.

    데이터랩은 Open API 기준으로 일간/주간/월간 상대지수를 제공하므로, 24시간 단위의
    실시간 조회수가 아니라 최근 일자 단위 관심도 보정값으로만 사용합니다.
    """
    keyword = clean_text(keyword)
    if not keyword or not naver_enabled() or not _env_true("USE_NAVER_DATALAB", "true"):
        return 0.0

    # 일간 데이터는 당일이 비어 있을 수 있어, 최근 3일 범위를 요청하고 나온 ratio만 사용합니다.
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    start_date = today - timedelta(days=max(2, int((lookback_hours or 24) / 24) + 1))
    end_date = today

    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": keyword[:20], "keywords": [keyword]}],
    }

    try:
        resp = requests.post(NAVER_DATALAB_API, headers={**_headers(), "Content-Type": "application/json"}, json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"[WARN] Naver DataLab API fetch failed for {keyword}: {exc}")
        return 0.0

    ratios = []
    for result in data.get("results", []):
        for row in result.get("data", []):
            try:
                ratios.append(float(row.get("ratio", 0) or 0))
            except Exception:
                pass
    if not ratios:
        return 0.0
    # 가장 최근 값에 가중치를 주되, 값이 없을 경우 평균 수준을 반영합니다.
    return round(max(ratios[-1], sum(ratios) / len(ratios)), 2)


FINANCE_NEWS_QUERIES = [
    "금리 환율 물가 경제",
    "대출 예금 금융 소비자",
    "코스피 코스닥 증시 주식",
    "부동산 전세 청약 대출",
    "소상공인 지원금 정책 금융",
]

GENERAL_NEWS_QUERIES = [
    "경제 금융 증시",
    "정책 사회 이슈",
    "생활 정보 제도",
    "산업 기업 기술",
    "부동산 교육 날씨",
]


def _candidate_from_title(title: str) -> str:
    title = _strip_tags(title)
    title = re.sub(r"\s+-\s+[^-]{2,20}$", "", title)
    title = re.sub(r"[\[\(].*?[\]\)]", " ", title)
    title = re.sub(r'["\'“”‘’]', "", title)
    title = re.sub(r"\s+", " ", title).strip(" .,:;!?…·|/-")
    # 너무 긴 제목은 텔레그램 후보로 보기 어렵기 때문에 핵심 앞부분만 사용합니다.
    words = title.split()
    if len(words) > 8:
        title = " ".join(words[:8])
    return title[:60].strip()


def collect_naver_news_candidates(limit: int = 30, lookback_hours: int = 24, category_filter: str = "finance") -> pd.DataFrame:
    """네이버 뉴스 검색 결과에서 최근 이슈 후보를 보강 수집합니다.

    네이버는 공식 Open API로 '실시간 인기검색어' 원본 랭킹을 제공하지 않으므로,
    카테고리성 검색어의 최신 뉴스 제목을 후보 아이템으로 보강합니다.
    """
    columns = ["keyword", "source", "approx_traffic", "collected_at", "published_at", "age_hours"]
    if not naver_enabled() or not _env_true("USE_NAVER_NEWS_CANDIDATES", "true"):
        return pd.DataFrame(columns=columns)

    raw_filter = str(category_filter or "finance").lower().strip()
    queries = GENERAL_NEWS_QUERIES if raw_filter in {"all", "전체", "*"} else FINANCE_NEWS_QUERIES

    rows = []
    seen = set()
    per_query = max(5, int(limit / max(1, len(queries))) + 3)
    for query in queries:
        for article in fetch_naver_news(query, limit=per_query, lookback_hours=lookback_hours, display=40):
            candidate = _candidate_from_title(article.get("title", ""))
            if not candidate or candidate in seen:
                continue
            if not is_valid_korean_keyword(candidate, allow_english=_env_true("ALLOW_ENGLISH_KEYWORDS", "false")):
                continue
            seen.add(candidate)
            rows.append({
                "keyword": candidate,
                "source": "naver_news_candidate_24h",
                "approx_traffic": 0,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "published_at": article.get("published_at", ""),
                "age_hours": article.get("age_hours", ""),
            })
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break

    return pd.DataFrame(rows, columns=columns)
