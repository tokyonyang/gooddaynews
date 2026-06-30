import os
import re
import html
import feedparser
import pandas as pd
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from seo_utils import clean_text, score_keyword, is_valid_korean_keyword

try:
    from naver_sources import collect_naver_news_candidates
except Exception:
    collect_naver_news_candidates = None

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"


def _parse_approx_traffic(value: str) -> int:
    """Google Trends RSS의 20K+, 1M+, 2만+ 같은 조회수 표현을 숫자로 변환합니다."""
    text = clean_text(value)
    if not text:
        return 0

    # 예: 20K+, 100K+ searches, 1.5M+
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KkMmBb])\+?", text)
    if m:
        number = float(m.group(1))
        unit = m.group(2).lower()
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(unit, 1)
        return int(number * multiplier)

    # 예: 2만+, 3천+
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(억|만|천)\+?", text)
    if m:
        number = float(m.group(1))
        multiplier = {"천": 1_000, "만": 10_000, "억": 100_000_000}.get(m.group(2), 1)
        return int(number * multiplier)

    m = re.search(r"(\d[\d,]*)", text)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


def _get_entry_approx_traffic(entry) -> int:
    candidates = [
        getattr(entry, "ht_approx_traffic", ""),
        getattr(entry, "approx_traffic", ""),
    ]
    try:
        candidates.append(entry.get("ht_approx_traffic", ""))
        candidates.append(entry.get("approx_traffic", ""))
    except Exception:
        pass
    candidates.append(getattr(entry, "summary", ""))

    for candidate in candidates:
        parsed = _parse_approx_traffic(candidate)
        if parsed:
            return parsed
    return 0


def _utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now() -> str:
    return _utc_now_dt().isoformat()


def _parse_entry_datetime(entry) -> datetime | None:
    """RSS entry의 published/updated 시간을 UTC datetime으로 변환합니다."""
    # feedparser가 구조화해준 값 우선 사용
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    # 문자열 날짜 fallback
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, "") or ""
        raw = clean_text(raw)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def _entry_age_hours(entry_dt: datetime | None) -> float | None:
    if entry_dt is None:
        return None
    return max(0.0, (_utc_now_dt() - entry_dt).total_seconds() / 3600)


def fetch_google_trends_rss(geo: str = "KR", limit: int = 30, lookback_hours: int = 24) -> pd.DataFrame:
    """Google Trends Trending Now RSS를 best-effort로 읽습니다.

    - 기본값은 최근 24시간 이내 entry를 우선 사용합니다.
    - Google Trends RSS가 항목별 published 시간을 제공하지 않는 경우가 있어,
      시간값이 없는 항목은 "현재 Trending RSS 목록"으로 간주해 유지합니다.
    """
    columns = ["keyword", "source", "approx_traffic", "collected_at", "published_at", "age_hours"]
    try:
        feed = feedparser.parse(GOOGLE_TRENDS_RSS.format(geo=geo))
        rows = []
        cutoff = _utc_now_dt() - timedelta(hours=max(1, int(lookback_hours or 24)))
        for e in feed.entries[:limit]:
            title = clean_text(html.unescape(getattr(e, "title", "")))
            summary = clean_text(html.unescape(getattr(e, "summary", "")))
            approx = _get_entry_approx_traffic(e)
            entry_dt = _parse_entry_datetime(e)

            # 시간이 명확하게 있고 24시간보다 오래된 항목은 제외합니다.
            if entry_dt is not None and entry_dt < cutoff:
                continue

            age = _entry_age_hours(entry_dt)
            if title:
                rows.append({
                    "keyword": title,
                    "source": "google_trends_rss_24h",
                    "approx_traffic": approx,
                    "collected_at": _utc_now(),
                    "published_at": entry_dt.isoformat() if entry_dt else "",
                    "age_hours": round(age, 2) if age is not None else "",
                })
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:
        print(f"[WARN] Google Trends RSS fetch failed: {exc}")
        return pd.DataFrame(columns=columns)


def load_seed_keywords(path: str = "data/seed_keywords.csv") -> pd.DataFrame:
    columns = ["keyword", "source", "approx_traffic", "collected_at", "published_at", "age_hours"]
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path)
    if "keyword" not in df.columns:
        return pd.DataFrame(columns=columns)
    if "source" not in df.columns:
        df["source"] = "seed"
    if "approx_traffic" not in df.columns:
        df["approx_traffic"] = 0
    df["collected_at"] = _utc_now()
    df["published_at"] = ""
    df["age_hours"] = ""
    return df[columns]


def collect_keywords(geo: str = "KR", limit: int = 30, lookback_hours: int = 24, include_seed_keywords: bool | None = None) -> pd.DataFrame:
    allow_english = os.environ.get("ALLOW_ENGLISH_KEYWORDS", "false").lower() in {"1", "true", "yes", "y"}
    if include_seed_keywords is None:
        include_seed_keywords = os.environ.get("INCLUDE_SEED_KEYWORDS", "false").lower() in {"1", "true", "yes", "y"}

    frames = [fetch_google_trends_rss(geo, limit, lookback_hours=lookback_hours)]

    # 네이버 뉴스 검색 API가 설정된 경우, 한국 뉴스 기반 후보를 보강합니다.
    # 네이버는 공식 API로 실시간 인기검색어 원본 순위를 제공하지 않으므로
    # 최신 뉴스 제목을 후보 아이템으로 추가하고, 최종 순위는 main.py에서 네이버 신호로 보정합니다.
    if collect_naver_news_candidates is not None:
        try:
            category_filter = os.environ.get("CATEGORY_FILTER", "finance")
            frames.append(collect_naver_news_candidates(limit=limit, lookback_hours=lookback_hours, category_filter=category_filter))
        except Exception as exc:
            print(f"[WARN] Naver news candidates skipped: {exc}")

    # 최신 24시간 운영에서는 seed 키워드가 오래된 주제를 섞을 수 있으므로 기본 제외합니다.
    if include_seed_keywords:
        frames.append(load_seed_keywords())

    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["keyword", "source", "approx_traffic", "collected_at", "published_at", "age_hours"])
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df

    df["keyword"] = df["keyword"].map(clean_text)
    df = df[df["keyword"] != ""].drop_duplicates("keyword")
    df = df[df["keyword"].map(lambda x: is_valid_korean_keyword(x, allow_english=allow_english))]

    if df.empty:
        return df.reset_index(drop=True)

    df["score"] = df.apply(
        lambda r: score_keyword(r["keyword"], r.get("source", ""), int(r.get("approx_traffic") or 0)),
        axis=1,
    )
    return df.sort_values(["score", "approx_traffic"], ascending=False).head(limit).reset_index(drop=True)
