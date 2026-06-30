import os
import argparse
import json
import re
import html as html_lib
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

import pandas as pd
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from trend_sources import collect_keywords
from content_generator import generate_article
from wp_publisher import create_wp_post
from telegram_notify import send_telegram, send_telegram_long, html_escape
from news_sources import fetch_related_news, fetch_global_breaking_news

try:
    from naver_sources import fetch_naver_datalab_score, fetch_naver_news_signal, naver_enabled
except Exception:
    fetch_naver_datalab_score = None
    fetch_naver_news_signal = None
    def naver_enabled():
        return False


# -----------------------------------------------------------------------------
# 카테고리 설정
# -----------------------------------------------------------------------------
# 기본 운영은 경제/금융 관련 카테고리만 사용합니다.
# CATEGORY_FILTER=all 로 바꾸면 전체 카테고리 사용,
# CATEGORY_FILTER=economy_finance,stock_investment 처럼 쉼표로 직접 지정할 수도 있습니다.
CATEGORY_GROUPS = OrderedDict({
    "economy_finance": {
        "label": "💰 경제·금융",
        "short_label": "경제·금융",
        "news_hint": "경제 금융 물가 금리 환율",
        "keywords": [
            "경제", "금융", "금리", "기준금리", "대출", "예금", "적금", "환율", "원달러", "원엔", "달러",
            "물가", "인플레이션", "소비자물가", "생산자물가", "전기요금", "가스요금", "공공요금",
            "카드", "신용카드", "체크카드", "보험", "자동차보험", "실손보험", "보험료",
            "연말정산", "세금", "종합소득세", "부가세", "소득공제", "환급", "재테크", "생활비",
        ],
    },
    "stock_investment": {
        "label": "📈 증권·투자",
        "short_label": "증권·투자",
        "news_hint": "증권 주식 코스피 투자 금융시장",
        "keywords": [
            "주식", "증시", "증권", "코스피", "코스닥", "나스닥", "S&P", "다우", "ETF", "펀드",
            "채권", "배당", "공모주", "청약", "IPO", "실적", "영업이익", "시가총액", "반도체",
            "삼성전자", "SK하이닉스", "엔비디아", "테슬라", "투자", "매수", "매도", "수익률",
        ],
    },
    "realestate_finance": {
        "label": "🏠 부동산·주거금융",
        "short_label": "부동산·주거금융",
        "news_hint": "부동산 주택 대출 전세 청약",
        "keywords": [
            "부동산", "아파트", "집값", "전세", "월세", "전월세", "매매가", "분양", "청약",
            "주택", "주담대", "주택담보대출", "전세대출", "DSR", "LTV", "DTI", "임대차",
            "공시가격", "재산세", "종부세", "취득세", "양도세",
        ],
    },
    "policy_support": {
        "label": "🏛️ 정책·지원금",
        "short_label": "정책·지원금",
        "news_hint": "정부 정책 지원금 소상공인 세제 금융",
        "keywords": [
            "지원금", "보조금", "장려금", "급여", "수당", "신청", "소상공인", "자영업", "중소기업",
            "민생", "추경", "정부지원", "정책자금", "대환대출", "새출발기금", "국민연금", "건강보험",
            "최저임금", "실업급여", "근로장려금", "자녀장려금",
        ],
    },
    "tech_business": {
        "label": "💻 산업·기업",
        "short_label": "산업·기업",
        "news_hint": "산업 기업 IT 테크 실적",
        "keywords": [
            "기업", "산업", "AI", "인공지능", "반도체", "배터리", "전기차", "자동차", "로봇", "클라우드",
            "스마트폰", "갤럭시", "아이폰", "수출", "공급망", "실적발표",
        ],
    },
    "living_policy": {
        "label": "🧾 생활·제도",
        "short_label": "생활·제도",
        "news_hint": "생활 제도 정책 소비자",
        "keywords": [
            "생활", "제도", "복지", "교통", "요금제", "알뜰폰", "택배", "소비자", "가격", "할인", "혜택",
        ],
    },
    "education": {
        "label": "🎓 교육·입시",
        "short_label": "교육·입시",
        "news_hint": "교육 입시 학교 대학",
        "keywords": ["교육", "입시", "대학", "수능", "모집", "학교", "학생", "학자금"],
    },
    "weather_safety": {
        "label": "🌦️ 날씨·안전",
        "short_label": "날씨·안전",
        "news_hint": "날씨 안전 재난",
        "keywords": ["날씨", "장마", "폭염", "태풍", "폭우", "호우", "재난", "안전", "지진"],
    },
    "other": {
        "label": "📰 기타",
        "short_label": "기타",
        "news_hint": "뉴스 이슈",
        "keywords": [],
    },
})

FINANCE_CATEGORY_IDS = [
    "economy_finance",
    "stock_investment",
    "realestate_finance",
    "policy_support",
]

# -----------------------------------------------------------------------------
# 글로벌 경제 위험 알림 기본값
# -----------------------------------------------------------------------------
# 오늘의 핫이슈와 섞지 않고 별도 섹션으로 보여줄 시장 충격형 이슈입니다.
# GitHub Variables의 GLOBAL_MACRO_ALERT_TOPICS 값으로 운영 중 교체할 수 있습니다.
GLOBAL_MACRO_DEFAULT_TOPICS = [
    "로이터 속보 글로벌 경제 시장",
    "블룸버그 속보 글로벌 시장 경제",
    "전쟁 확전 지정학 리스크 유가",
    "질병 감염병 WHO 팬데믹 경제",
    "원달러 환율 급등 급락 외환시장",
    "국제유가 급등 급락 OPEC 원유",
    "원자재 급등 급락 금 구리 곡물",
    "미국 기준금리 연준 FOMC 국채금리",
    "달러인덱스 미국 국채금리 급등",
    "시장 루머 가십 기업 인수합병 제재",
    "미중 갈등 관세 제재 공급망",
]

GLOBAL_MACRO_RISK_RULES = OrderedDict({
    "전쟁·지정학": [
        "전쟁", "확전", "공습", "침공", "미사일", "휴전", "제재", "지정학", "중동", "호르무즈",
        "우크라이나", "러시아", "이스라엘", "이란", "대만", "중국군", "war", "attack", "missile", "sanction",
    ],
    "질병·감염병": [
        "질병", "감염병", "팬데믹", "전염병", "WHO", "코로나", "조류독감", "독감", "바이러스",
        "disease", "pandemic", "virus", "outbreak",
    ],
    "환율·달러": [
        "원달러", "원·달러", "환율", "달러", "외환", "달러인덱스", "DXY", "yen", "yuan", "currency", "forex",
    ],
    "원자재·유가": [
        "원자재", "국제유가", "유가", "원유", "브렌트", "WTI", "OPEC", "금값", "금 가격", "구리",
        "곡물", "밀", "쌀", "대두", "commodity", "oil", "gold", "copper", "grain",
    ],
    "금리·채권": [
        "금리", "기준금리", "연준", "FOMC", "파월", "국채금리", "채권", "수익률", "긴축", "인하",
        "rate", "fed", "fomc", "treasury", "yield",
    ],
    "시장루머·가십": [
        "루머", "가십", "소문", "설", "인수설", "매각설", "합병설", "market talk", "rumor", "gossip",
    ],
    "글로벌속보": [
        "로이터", "블룸버그", "reuters", "bloomberg", "속보", "breaking", "markets", "global economy",
    ],
})

GLOBAL_MACRO_IMPACT_HINTS = {
    "전쟁·지정학": "유가·금값·방산·해운·환율 변동 가능성",
    "질병·감염병": "여행·항공·소비·공급망 위축 가능성",
    "환율·달러": "수입물가·해외직구 원가·외국인 수급 영향",
    "원자재·유가": "물가·운송비·식품/에너지 비용 영향",
    "금리·채권": "대출금리·주식 밸류에이션·부동산 심리 영향",
    "시장루머·가십": "단기 변동성 확대 가능성. 확인 전 과신 금지",
    "글로벌속보": "글로벌 증시·환율·원자재 방향성 확인 필요",
}



def _env_true(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}



def _short_error(exc: Exception, max_len: int = 240) -> str:
    text = str(exc).replace("\\n", " ").replace("\n", " ").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")



def _parse_topics(text: str) -> list[str]:
    """GitHub Actions 수동 입력값에서 선택 주제를 추출합니다.

    쉼표, 줄바꿈, 세미콜론으로 구분합니다. 공백만으로는 나누지 않습니다.
    """
    text = str(text or "").strip()
    if not text:
        return []
    parts = re.split(r"[\n,;，、]+", text)
    topics = []
    seen = set()
    for part in parts:
        item = re.sub(r"\s+", " ", part).strip(" -•\t")
        if item and item not in seen:
            seen.add(item)
            topics.append(item)
    return topics



def _global_macro_topics_from_env(value: str) -> list[str]:
    """글로벌 경제 위험 알림용 검색어를 반환합니다.

    GLOBAL_MACRO_ALERT_TOPICS가 비어 있으면 기본 위험 키워드 묶음을 사용합니다.
    """
    topics = _parse_topics(value)
    return topics or GLOBAL_MACRO_DEFAULT_TOPICS[:]


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[가-힣]", str(text or "")))


def _macro_risk_label(text: str) -> str:
    haystack = str(text or "").lower()
    best_label = "글로벌속보"
    best_score = 0
    for label, keywords in GLOBAL_MACRO_RISK_RULES.items():
        score = 0
        for kw in keywords:
            needle = str(kw or "").lower()
            if needle and needle in haystack:
                score += max(1, len(needle))
        if score > best_score:
            best_label = label
            best_score = score
    return best_label


def _macro_risk_emoji(label: str) -> str:
    return {
        "전쟁·지정학": "⚠️",
        "질병·감염병": "🦠",
        "환율·달러": "💱",
        "원자재·유가": "🛢️",
        "금리·채권": "🏦",
        "시장루머·가십": "🗣️",
        "글로벌속보": "🚨",
    }.get(label, "🚨")


def _macro_impact_hint(label: str) -> str:
    return GLOBAL_MACRO_IMPACT_HINTS.get(label, GLOBAL_MACRO_IMPACT_HINTS["글로벌속보"])


def _macro_source_label(article: dict) -> str:
    text = f"{article.get('source', '')} {article.get('title', '')}"
    lowered = text.lower()
    labels = []
    if "reuters" in lowered or "로이터" in text:
        labels.append("로이터")
    if "bloomberg" in lowered or "블룸버그" in text:
        labels.append("블룸버그")
    if labels:
        return "/".join(labels)
    return str(article.get("source") or "뉴스")


def _macro_source_score(article: dict) -> int:
    text = f"{article.get('source', '')} {article.get('title', '')}".lower()
    score = 0
    if "reuters" in text or "로이터" in text:
        score += 350
    if "bloomberg" in text or "블룸버그" in text:
        score += 350
    return score


def _macro_urgency_score(text: str) -> int:
    lowered = str(text or "").lower()
    urgent_terms = [
        "속보", "긴급", "급등", "급락", "폭등", "폭락", "확전", "공습", "제재", "쇼크", "위기",
        "breaking", "surge", "plunge", "jump", "slump", "crisis", "shock",
    ]
    return sum(80 for term in urgent_terms if term in lowered)


def _macro_alert_display_title(article: dict, topic: str, label: str) -> str:
    """텔레그램에서 제목만 봐도 성격을 알 수 있게 한국어 제목을 만듭니다."""
    original = clean_title = re.sub(r"\s+", " ", str(article.get("title") or "")).strip()
    source_label = _macro_source_label(article)

    # 한국어 제목이면 원 제목을 살리되 앞에 출처/위험 태그가 붙으므로 과도하게 손대지 않습니다.
    if clean_title and _contains_hangul(clean_title):
        return clean_title[:120]

    # 영문 Reuters/Bloomberg 제목은 정확한 기계번역 API 없이 오역하지 않도록,
    # 검색 주제와 위험 태그를 이용해 한국어 요약 제목으로 표시합니다.
    topic_ko = re.sub(r"\s+", " ", str(topic or "글로벌 경제 속보")).strip()
    topic_ko = re.sub(r"\b(Reuters|Bloomberg|breaking|markets|global economy)\b", "", topic_ko, flags=re.IGNORECASE).strip()
    topic_ko = topic_ko or "글로벌 경제 속보"
    return f"{source_label} 확인 필요: {topic_ko}"[:120]


def _macro_alert_score(article: dict, topic: str, label: str) -> int:
    text = f"{article.get('title', '')} {article.get('source', '')} {topic}"
    score = _macro_source_score(article) + _macro_urgency_score(text)
    # 최근일수록 위로 올립니다.
    try:
        age = float(article.get("age_hours", 999) or 999)
    except Exception:
        age = 999
    if age <= 3:
        score += 180
    elif age <= 6:
        score += 120
    elif age <= 12:
        score += 60
    if label in {"전쟁·지정학", "환율·달러", "원자재·유가", "금리·채권"}:
        score += 120
    return score


def _build_global_macro_alert_items(
    enabled: bool,
    topics: list[str],
    geo: str,
    links_per_topic: int,
    lookback_hours: int,
    max_items: int,
) -> list[dict]:
    """전쟁/질병/환율/원자재/금리/루머 등 글로벌 경제 충격 가능 이슈를 별도 섹션으로 구성합니다."""
    if not enabled:
        return []

    rows: list[dict] = []
    seen = set()
    per_topic_limit = max(2, min(8, int(links_per_topic or 5)))

    for topic in topics:
        articles = fetch_related_news(
            topic,
            limit=per_topic_limit,
            geo=geo,
            category_hint="로이터 블룸버그 Reuters Bloomberg 속보 글로벌 경제 시장 환율 유가 금리 원자재",
            lookback_hours=lookback_hours,
        )
        for article in articles:
            title = str(article.get("title") or "").strip()
            url = str(article.get("url") or "").strip()
            key = re.sub(r"\s+", " ", title.lower()) or url
            if not title or not url or key in seen:
                continue
            seen.add(key)
            label = _macro_risk_label(f"{topic} {title} {article.get('source', '')}")
            source_label = _macro_source_label(article)
            display_title = _macro_alert_display_title(article, topic, label)
            score = _macro_alert_score(article, topic, label)
            rows.append({
                "keyword": display_title,
                "alert_title": display_title,
                "original_title": title,
                "query": topic,
                "risk_label": label,
                "risk_emoji": _macro_risk_emoji(label),
                "market_impact": _macro_impact_hint(label),
                "source_label": source_label,
                "published": article.get("published", ""),
                "published_at": article.get("published_at", ""),
                "age_hours": article.get("age_hours", ""),
                "score": score,
                "news": [article],
            })

    rows.sort(key=lambda item: (_to_int(item.get("score")), str(item.get("published_at", ""))), reverse=True)
    return rows[: max(0, int(max_items or 7))]



def _parse_category_filter(value: str) -> list[str]:
    """카테고리 필터 문자열을 실제 category id 목록으로 변환합니다.

    지원값:
    - finance, economy, 경제, 금융: 경제/금융 관련 4개 그룹만 사용
    - all, 전체: 전체 카테고리 사용
    - economy_finance,stock_investment 처럼 직접 지정
    """
    raw = str(value or "finance").strip()
    if not raw:
        raw = "finance"
    lowered = raw.lower().replace(" ", "")

    if lowered in {"all", "전체", "*"}:
        return list(CATEGORY_GROUPS.keys())
    if lowered in {"finance", "economy", "money", "경제", "금융", "경제금융", "경제·금융"}:
        return FINANCE_CATEGORY_IDS[:]

    aliases = {
        "경제금융": "economy_finance",
        "경제·금융": "economy_finance",
        "경제": "economy_finance",
        "금융": "economy_finance",
        "주식": "stock_investment",
        "증권": "stock_investment",
        "투자": "stock_investment",
        "부동산": "realestate_finance",
        "주거금융": "realestate_finance",
        "지원금": "policy_support",
        "정책": "policy_support",
        "산업": "tech_business",
        "기업": "tech_business",
        "생활": "living_policy",
        "교육": "education",
        "날씨": "weather_safety",
        "기타": "other",
    }

    selected = []
    for part in re.split(r"[\n,;，、]+", raw):
        token = part.strip()
        if not token:
            continue
        key = token.lower().replace(" ", "")
        category_id = aliases.get(token) or aliases.get(key) or key
        if category_id in CATEGORY_GROUPS and category_id not in selected:
            selected.append(category_id)

    return selected or FINANCE_CATEGORY_IDS[:]



def _classify_keyword(keyword: str) -> str:
    """키워드를 카테고리 그룹으로 분류합니다.

    finance 기본 필터에서 너무 넓은 일반 이슈가 섞이지 않도록, 명시적인 키워드 매칭 기반으로 분류합니다.
    """
    text = str(keyword or "")
    normalized = text.lower().replace(" ", "")
    best_category = "other"
    best_score = 0

    for category_id, config in CATEGORY_GROUPS.items():
        if category_id == "other":
            continue
        score = 0
        for kw in config.get("keywords", []):
            kw_text = str(kw).lower().replace(" ", "")
            if not kw_text:
                continue
            if kw_text in normalized:
                # 긴 키워드를 더 강하게 반영합니다. 예: 기준금리 > 금리
                score += max(1, len(kw_text))
        if score > best_score:
            best_score = score
            best_category = category_id

    return best_category



def _category_label(category_id: str) -> str:
    return CATEGORY_GROUPS.get(category_id, CATEGORY_GROUPS["other"]).get("label", category_id)



def _category_short_label(category_id: str) -> str:
    return CATEGORY_GROUPS.get(category_id, CATEGORY_GROUPS["other"]).get("short_label", category_id)



def _category_news_hint(category_id: str) -> str:
    return CATEGORY_GROUPS.get(category_id, CATEGORY_GROUPS["other"]).get("news_hint", "")



def _article_to_plain_text(article: dict) -> str:
    """WordPress HTML 초안을 텔레그램에서 읽기 쉬운 plain text로 변환합니다."""
    html = article.get("html") or ""
    soup = BeautifulSoup(html, "html.parser")

    # 제목형 태그 앞뒤에 여백을 넣어 가독성을 높입니다.
    for tag in soup.find_all(["h1", "h2", "h3"]):
        tag.insert_before("\n\n")
        tag.insert_after("\n")
    for tag in soup.find_all(["p", "li", "tr"]):
        tag.insert_after("\n")

    body = soup.get_text("\n", strip=True)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    tags = article.get("tags") if isinstance(article.get("tags"), list) else []
    tag_text = ", ".join(str(t) for t in tags[:8])

    lines = [
        "📝 AdSense SEO 글 초안",
        f"주제: {article.get('keyword') or ''}",
        f"제목: {article.get('title') or '제목 없음'}",
    ]
    if article.get("meta_description"):
        lines.append(f"메타설명: {article.get('meta_description')}")
    if tag_text:
        lines.append(f"태그: {tag_text}")
    lines.append("\n본문")
    lines.append(body or "본문 생성 결과가 비어 있습니다.")
    return "\n".join(lines)



def _keyword_dataframe_from_topics(topics: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{
        "keyword": topic,
        "source": "manual_topic",
        "approx_traffic": 0,
        "published_at": "",
        "age_hours": "",
    } for topic in topics])



def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _to_int(value, default: int = 0) -> int:
    """조회수/트래픽 값을 정수로 안전하게 변환합니다."""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9]", "", value)
            return int(cleaned) if cleaned else default
        return int(float(value))
    except Exception:
        return default


def _traffic_label(value) -> str:
    """텔레그램에 표시할 조회수 라벨을 만듭니다."""
    n = _to_int(value)
    if n <= 0:
        return "조회수 정보 없음"
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}억+"
    if n >= 10_000:
        return f"{n / 10_000:.1f}만+"
    return f"{n:,}+"




def _interest_label(value) -> str:
    n = _to_int(value)
    if n <= 0:
        return "관심도 산정 중"
    return f"{n:,}점"


def _calculate_composite_score(traffic: int, naver_news_count: int, naver_datalab_score: float, base_score: int = 0) -> int:
    """핫이슈 정렬용 종합 관심도 점수입니다.

    - traffic: Google Trends approx traffic. 절대 검색량이 아니라 Google RSS가 제공하는 대략값입니다.
    - naver_news_count: 최근 lookback_hours 안에 확인된 네이버 뉴스 기사 수.
    - naver_datalab_score: 네이버 데이터랩 상대 검색지수. 절대 조회수가 아니라 0~100 상대값입니다.
    """
    traffic_component = min(_to_int(traffic), 1_000_000)
    news_component = min(_to_int(naver_news_count), 50) * 8_000
    datalab_component = int(min(float(naver_datalab_score or 0), 100.0) * 5_000)
    base_component = min(_to_int(base_score), 500)
    return int(traffic_component + news_component + datalab_component + base_component)

def _rank_sort_key(row_or_item):
    """종합 관심도 우선 정렬 key입니다.

    네이버 Open API는 기사/검색어의 절대 조회수를 제공하지 않으므로,
    Google Trends approx traffic + 네이버 뉴스량 + 네이버 데이터랩 상대지수를 합산한
    composite_score를 우선 사용합니다.
    """
    getter = row_or_item.get
    composite = _to_int(getter("composite_score", 0))
    traffic = _to_int(getter("approx_traffic_int", getter("approx_traffic", 0)))
    datalab = float(getter("naver_datalab_score", 0) or 0)
    naver_news_count = _to_int(getter("naver_news_count", 0))
    news_count = len(getter("news", []) or [])
    score = _to_int(getter("score", 0))
    return (composite, traffic, datalab, naver_news_count, news_count, score)



def _build_item_angle(keyword: str, category_id: str = "other") -> str:
    """글을 바로 작성하지 않고, 사람이 판단하기 좋은 작성 방향만 짧게 제안합니다."""
    k = str(keyword or "")
    if category_id == "economy_finance":
        if any(word in k for word in ["금리", "대출", "예금", "적금"]):
            return "금리 변화 → 가계부담/저축전략 → 확인할 금융상품 포인트"
        if any(word in k for word in ["물가", "전기요금", "가스요금", "공공요금", "생활비"]):
            return "가격 변화 배경 → 가계 영향 → 절약·대응 체크리스트"
        if any(word in k for word in ["환율", "달러", "원엔", "원달러"]):
            return "환율 변동 원인 → 수입물가/여행/투자 영향 → 체크포인트"
        return "경제 이슈 배경 → 내 지갑에 미치는 영향 → 실전 대응 순서"
    if category_id == "stock_investment":
        return "시장 변동 원인 → 관련 업종/종목 영향 → 개인투자자가 확인할 지표"
    if category_id == "realestate_finance":
        return "가격·정책 변화 → 실수요자 영향 → 청약/대출/전월세 체크포인트"
    if category_id == "policy_support":
        return "대상·신청기간·필요서류·주의사항 중심의 실용형 정리"

    if any(word in k for word in ["지원금", "신청", "환급", "보조금"]):
        return "대상·신청기간·필요서류·주의사항 중심의 실용형 정리"
    if any(word in k for word in ["전기요금", "가스요금", "난방비", "절약", "요금"]):
        return "가정에서 바로 적용 가능한 절약 방법과 요금제 확인 포인트"
    if any(word in k for word in ["대학", "입시", "모집", "수능", "교육"]):
        return "일정·대상·변경사항·체크리스트 중심의 정보형 글"
    if any(word in k for word in ["장마", "폭염", "태풍", "날씨", "폭우"]):
        return "대비 체크리스트·피해 예방·생활 안전 수칙 중심"
    if any(word in k for word in ["부동산", "청약", "주택", "전세", "월세"]):
        return "자격·일정·비용·리스크를 분리한 생활경제형 정리"
    return "이슈 배경 → 왜 관심이 커졌는지 → 독자가 확인할 것 순서로 정리"



def _prepare_keywords_with_categories(keywords: pd.DataFrame, allowed_categories: list[str]) -> pd.DataFrame:
    """키워드에 카테고리 컬럼을 붙이고, 허용 카테고리만 남긴 뒤 조회수 우선순으로 정렬합니다."""
    if keywords.empty:
        return keywords

    df = keywords.copy()
    df["category_id"] = df["keyword"].map(_classify_keyword)
    df["category_label"] = df["category_id"].map(_category_short_label)
    if "approx_traffic" not in df.columns:
        df["approx_traffic"] = 0
    df["approx_traffic_int"] = df["approx_traffic"].map(_to_int)
    if "score" not in df.columns:
        df["score"] = 0
    df["score"] = df["score"].map(_to_int)

    if allowed_categories:
        df = df[df["category_id"].isin(allowed_categories)]

    # 핵심 변경: 총 항목을 조회수 많은 순으로 먼저 정렬합니다.
    # 조회수가 같은 항목은 내부 점수와 원래 순서를 보조 기준으로 사용합니다.
    df = df.sort_values(["approx_traffic_int", "score"], ascending=[False, False])
    return df.reset_index(drop=True)



def _build_idea_digest(keywords: pd.DataFrame, max_items: int, links_per_topic: int, geo: str, lookback_hours: int = 24) -> list[dict]:
    """조회수 높은 순으로 작성 후보 아이템을 만들고 근거 뉴스 링크를 붙입니다."""
    items = []
    if keywords.empty:
        return items

    df = keywords.copy()
    if "approx_traffic" not in df.columns:
        df["approx_traffic"] = 0
    if "approx_traffic_int" not in df.columns:
        df["approx_traffic_int"] = df["approx_traffic"].map(_to_int)
    if "score" not in df.columns:
        df["score"] = 0
    df = df.sort_values(["approx_traffic_int", "score"], ascending=[False, False]).reset_index(drop=True)

    for rank, (_, row) in enumerate(df.iterrows(), 1):
        if len(items) >= max_items:
            break
        keyword = str(row.get("keyword", "")).strip()
        if not keyword:
            continue
        category_id = str(row.get("category_id") or _classify_keyword(keyword))
        news = fetch_related_news(
            keyword,
            limit=links_per_topic,
            geo=geo,
            category_hint=_category_news_hint(category_id),
            lookback_hours=lookback_hours,
        )
        approx_traffic = _to_int(row.get("approx_traffic_int", row.get("approx_traffic", 0)))
        base_score = _to_int(row.get("score", 0))

        naver_news_count = 0
        naver_news_latest_at = ""
        if fetch_naver_news_signal is not None and naver_enabled():
            try:
                signal = fetch_naver_news_signal(keyword, lookback_hours=lookback_hours, display=30)
                naver_news_count = _to_int(signal.get("naver_news_count", 0))
                naver_news_latest_at = str(signal.get("naver_news_latest_at", ""))
            except Exception as exc:
                print(f"[WARN] Naver news signal skipped for {keyword}: {exc}")

        naver_datalab_score = 0.0
        if fetch_naver_datalab_score is not None and naver_enabled():
            try:
                naver_datalab_score = float(fetch_naver_datalab_score(keyword, lookback_hours=lookback_hours) or 0)
            except Exception as exc:
                print(f"[WARN] Naver DataLab signal skipped for {keyword}: {exc}")

        composite_score = _calculate_composite_score(
            approx_traffic,
            naver_news_count or len([n for n in news if str(n.get("provider", "")).startswith("naver")]),
            naver_datalab_score,
            base_score,
        )

        item = {
            "rank": rank,
            "keyword": keyword,
            "source": str(row.get("source", "")),
            "published_at": str(row.get("published_at", "")),
            "age_hours": row.get("age_hours", ""),
            "approx_traffic": approx_traffic,
            "traffic_label": _traffic_label(approx_traffic),
            "score": base_score,
            "composite_score": composite_score,
            "interest_label": _interest_label(composite_score),
            "naver_news_count": naver_news_count,
            "naver_news_latest_at": naver_news_latest_at,
            "naver_datalab_score": naver_datalab_score,
            "category_id": category_id,
            "category_label": _category_short_label(category_id),
            "angle": _build_item_angle(keyword, category_id),
            "news": news,
        }
        item["news_count"] = len(news)
        item["evidence_strength"] = _evidence_strength(item)
        item["card_news_angle"] = _card_news_angle(item)
        item["article_angle"] = _article_angle(item)
        items.append(item)

    return sorted(items, key=_rank_sort_key, reverse=True)





def _evidence_item_count(items: list[dict]) -> int:
    """근거 뉴스가 1개 이상 붙은 항목 수입니다."""
    return sum(1 for item in items if len(item.get("news") or []) > 0)


def _fallback_stage_label(categories: list[str], lookback_hours: int) -> str:
    return f"{_allowed_label(categories)} / 최근 {int(lookback_hours)}시간"


def _collect_keywords_for_stage(
    args,
    topics: list[str],
    allowed_categories: list[str],
    include_seed_keywords: bool,
    lookback_hours: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """단계별 키워드 수집 + 카테고리 필터링을 수행합니다."""
    if topics:
        raw_keywords = _keyword_dataframe_from_topics(topics).head(args.max_keywords)
    else:
        # 카테고리 필터링 후에도 충분한 후보가 남도록 원본은 여유 있게 가져옵니다.
        raw_limit = max(args.max_keywords * 4, args.max_posts * 8, 100)
        raw_keywords = collect_keywords(
            args.geo,
            raw_limit,
            lookback_hours=lookback_hours,
            include_seed_keywords=include_seed_keywords,
        )
    prepared = _prepare_keywords_with_categories(raw_keywords, allowed_categories).head(args.max_keywords)
    return raw_keywords, prepared


def _build_idea_digest_with_fallback(
    args,
    topics: list[str],
    initial_categories: list[str],
    include_seed_keywords: bool,
    max_items: int,
    links_per_topic: int,
    base_lookback_hours: int,
    auto_fallback: bool = True,
    fallback_lookback_hours: int = 48,
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame, list[str], int, list[dict]]:
    """후보가 없거나 근거 기사가 전혀 없을 때 자동으로 범위를 확장합니다.

    단계:
    1. 요청 카테고리 + 최근 24시간
    2. 전체 카테고리 + 최근 24시간
    3. 전체 카테고리 + 최근 48시간
    """
    all_categories = list(CATEGORY_GROUPS.keys())
    base_hours = max(1, int(base_lookback_hours or 24))
    fallback_hours = max(base_hours, int(fallback_lookback_hours or 48))

    stages: list[tuple[str, list[str], int]] = [
        ("기본 검색", initial_categories, base_hours),
    ]
    if auto_fallback and set(initial_categories) != set(all_categories):
        stages.append(("카테고리 전체 확장", all_categories, base_hours))
    if auto_fallback and fallback_hours > base_hours:
        stages.append(("시간 범위 48시간 확장", all_categories, fallback_hours))

    fallback_info: list[dict] = []
    best_payload = None

    for stage_name, stage_categories, stage_hours in stages:
        raw_keywords, prepared_keywords = _collect_keywords_for_stage(
            args,
            topics,
            stage_categories,
            include_seed_keywords,
            stage_hours,
        )
        items = _build_idea_digest(
            prepared_keywords,
            max_items,
            links_per_topic,
            args.geo,
            lookback_hours=stage_hours,
        )
        evidence_count = _evidence_item_count(items)
        info = {
            "name": stage_name,
            "label": _fallback_stage_label(stage_categories, stage_hours),
            "category_ids": stage_categories,
            "lookback_hours": stage_hours,
            "keyword_count": int(len(prepared_keywords)),
            "item_count": int(len(items)),
            "evidence_count": int(evidence_count),
            "used": False,
        }
        fallback_info.append(info)

        payload = (items, raw_keywords, prepared_keywords, stage_categories, stage_hours, fallback_info)
        # 최종 실패 시에도 빈 결과보다 후보가 있는 결과를 보여주기 위한 보관값입니다.
        if best_payload is None or (evidence_count, len(items)) > (_evidence_item_count(best_payload[0]), len(best_payload[0])):
            best_payload = payload

        # 근거 기사까지 1개 이상 붙은 후보가 있으면 그 단계를 사용합니다.
        if items and evidence_count > 0:
            info["used"] = True
            return payload

    # 그래도 근거 있는 후보가 없으면 가장 나은 단계 결과를 사용합니다.
    if best_payload is not None:
        items, raw_keywords, prepared_keywords, stage_categories, stage_hours, info_list = best_payload
        # 동일한 info 객체를 찾아 사용 표시합니다.
        for info in info_list:
            if info.get("category_ids") == stage_categories and int(info.get("lookback_hours", 0)) == int(stage_hours):
                info["used"] = True
                break
        return best_payload

    return [], pd.DataFrame(), pd.DataFrame(), initial_categories, base_hours, fallback_info


def _html_attr(text: str) -> str:
    """HTML 링크 속성에 넣을 값을 안전하게 이스케이프합니다."""
    return html_lib.escape(str(text or ""), quote=True)



def _evidence_strength(item: dict) -> str:
    traffic = _to_int(item.get("approx_traffic"))
    news_count = len(item.get("news") or [])
    if traffic >= 100_000 or news_count >= 5:
        return "강함"
    if traffic >= 10_000 or news_count >= 3:
        return "보통"
    if traffic > 0 or news_count > 0:
        return "낮음"
    return "보강 필요"



def _card_news_angle(item: dict) -> str:
    keyword = item.get("keyword", "")
    category_id = item.get("category_id", "other")
    if category_id == "stock_investment":
        return "왜 올랐나/왜 내렸나 → 관련 업종 영향 → 개인투자자 체크포인트 5장 구성"
    if category_id == "realestate_finance":
        return "정책·금리 변화 → 실수요자 영향 → 대출/청약 체크리스트 카드 구성"
    if category_id == "policy_support":
        return "누가 받을 수 있나 → 신청기간 → 필요서류 → 주의사항 카드 구성"
    if any(w in keyword for w in ["금리", "환율", "물가", "요금"]):
        return "원인 → 가계 영향 → 오늘 확인할 숫자 → 대응법 카드 구성"
    return "핵심 원인 → 영향받는 사람 → 확인할 자료 → 대응 체크리스트 카드 구성"



def _article_angle(item: dict) -> str:
    keyword = item.get("keyword", "")
    category_id = item.get("category_id", "other")
    if category_id == "policy_support":
        return f"{keyword} 대상·신청방법·주의사항을 한 번에 정리하는 정보형 글"
    if category_id == "economy_finance":
        return f"{keyword} 배경과 가계/금융상품 영향, 확인해야 할 지표를 정리하는 해설형 글"
    if category_id == "stock_investment":
        return f"{keyword} 이슈가 시장과 관련 업종에 미치는 영향을 정리하는 투자 참고형 글"
    if category_id == "realestate_finance":
        return f"{keyword}이 실수요자와 대출·청약에 미치는 영향을 정리하는 생활경제형 글"
    return f"{keyword} 핵심 배경과 독자가 확인할 체크포인트를 정리하는 글"



def _select_card_news_items(items: list[dict], count: int) -> list[dict]:
    """카드뉴스로 만들기 좋은 항목을 고릅니다. 조회수와 근거자료가 있는 항목을 우선합니다."""
    preferred = {"economy_finance", "stock_investment", "realestate_finance", "policy_support"}
    ranked = sorted(
        items,
        key=lambda item: (
            _to_int(item.get("composite_score")),
            _to_int(item.get("approx_traffic")),
            1 if item.get("category_id") in preferred else 0,
            len(item.get("news") or []),
            _to_int(item.get("score")),
        ),
        reverse=True,
    )
    return ranked[: max(0, count)]



def _select_article_items(items: list[dict], count: int) -> list[dict]:
    """작성글로 만들기 좋은 항목을 고릅니다. 검색 유입형/실용형 주제를 조금 더 우선합니다."""
    practical_categories = {"policy_support", "economy_finance", "realestate_finance"}
    ranked = sorted(
        items,
        key=lambda item: (
            1 if item.get("category_id") in practical_categories else 0,
            _to_int(item.get("composite_score")),
            _to_int(item.get("approx_traffic")),
            len(item.get("news") or []),
            _to_int(item.get("score")),
        ),
        reverse=True,
    )
    return ranked[: max(0, count)]



def _news_links_html(news: list[dict], limit: int | None = None) -> str:
    """뉴스 링크를 링크1~링크N 라벨로 변환합니다."""
    if not news:
        return "지정 기간 기준 RSS에서 확인된 링크가 없습니다."

    parts = []
    selected = news[:limit] if limit else news
    for n, article in enumerate(selected, 1):
        title = html_escape(article.get("title") or "기사 제목 없음")
        media = html_escape(article.get("source") or "")
        published = html_escape(article.get("published") or "")
        url = str(article.get("url") or "").strip()
        meta = " · ".join(x for x in [media, published] if x)
        link_label = f"링크{n}"
        if url.startswith(("http://", "https://")):
            link_text = f'<a href="{_html_attr(url)}">{link_label}</a>'
        else:
            link_text = link_label
        if meta:
            parts.append(f"  {n}) {title} ({meta}) / {link_text}")
        else:
            parts.append(f"  {n}) {title} / {link_text}")
    return "\n".join(parts)



def _allowed_label(allowed_categories: list[str]) -> str:
    if allowed_categories == FINANCE_CATEGORY_IDS:
        return "경제·금융 우선"
    if allowed_categories:
        return ", ".join(_category_short_label(c) for c in allowed_categories)
    return "전체"



def _breaking_emoji(label: str) -> str:
    return {
        "전쟁·지정학": "⚠️",
        "질병·감염병": "🦠",
        "환율·달러": "💱",
        "원자재·유가": "🛢️",
        "금리·채권": "🏦",
        "무역·관세": "🚢",
        "금융시장": "📉",
        "기업·빅테크": "🏢",
        "영향력 인물 발언/SNS": "📣",
        "글로벌경제": "🚨",
    }.get(str(label or ""), "🚨")


def _breaking_provider_label(provider: str) -> str:
    return {
        "google_news": "Google News RSS",
        "news_site_rss": "실제 뉴스 사이트 RSS",
        "official_feed": "공식 기관 피드",
        "custom_social_or_feed": "SNS/사용자 지정 피드",
    }.get(str(provider or ""), str(provider or "뉴스"))


def _breaking_display_title(article: dict) -> str:
    """제목만 봐도 성격을 알 수 있도록 한국어 표시 제목을 만듭니다."""
    original = re.sub(r"\s+", " ", str(article.get("title") or "")).strip()
    if original and _contains_hangul(original):
        return original[:130]
    label = str(article.get("impact_label") or "글로벌경제")
    source = str(article.get("source") or "글로벌 뉴스")
    reason = str(article.get("impact_reason") or "글로벌 경제·시장 영향 확인 필요")
    return f"{source} 속보: {label} 이슈 — {reason}"[:130]


def _append_global_breaking_news_section(
    lines: list[str],
    items: list[dict] | None,
    title: str,
    lookback_hours: int,
) -> None:
    """경제 영향 가능 글로벌 속보 최신 3개 섹션을 추가합니다."""
    if not items:
        return

    lines.append("\n{}".format(f"<b>{html_escape(title)}</b>"))
    lines.append(f"기준: 최근 <b>{int(lookback_hours)}시간</b> 이내 / 경제영향 필터 통과 기사 중 <b>발행시각 최신순</b>")
    lines.append("보조수집: Google News RSS가 부족하면 실제 뉴스 사이트·공식기관 RSS·사용자 지정 SNS/RSS 피드를 함께 확인")

    for idx, article in enumerate(items, 1):
        label = html_escape(article.get("impact_label") or "글로벌경제")
        emoji = html_escape(_breaking_emoji(article.get("impact_label") or ""))
        headline = html_escape(_breaking_display_title(article))
        source = html_escape(article.get("source") or "뉴스")
        published = html_escape(article.get("published") or "")
        provider = html_escape(_breaking_provider_label(article.get("provider") or ""))
        reason = html_escape(article.get("impact_reason") or "글로벌 경제·시장 영향 확인 필요")
        original_title = str(article.get("title") or "").strip()
        display_title = _breaking_display_title(article)
        url = str(article.get("url") or "").strip()

        lines.append(f"\n<b>{idx}. {emoji} [{label}] {headline}</b>")
        meta = f"출처: <b>{source}</b> / 수집: {provider}"
        if published:
            meta += f" / 발행: {published}"
        lines.append(meta)
        lines.append(f"경제영향: {reason}")
        if original_title and original_title != display_title:
            lines.append(f"원문제목: {html_escape(original_title[:180])}")
        if url.startswith(("http://", "https://")):
            lines.append(f"근거자료: <a href=\"{_html_attr(url)}\">링크1</a>")
        else:
            lines.append("근거자료: 링크 없음")


def _append_global_macro_alert_section(lines: list[str], items: list[dict] | None, title: str) -> None:
    """전쟁/질병/환율/원자재/금리/루머 등 글로벌 경제 위험 알림 섹션을 추가합니다."""
    if not items:
        return

    lines.append("\n{}".format(f"<b>{html_escape(title)}</b>"))
    lines.append("대상: 전쟁·질병·환율·원자재·금리·시장루머 및 로이터/블룸버그 속보성 기사")
    lines.append("표시방식: 제목 앞에 위험 태그를 붙여 제목만 봐도 성격을 알 수 있게 정리")

    for idx, item in enumerate(items, 1):
        risk_label = html_escape(item.get("risk_label") or "글로벌속보")
        emoji = html_escape(item.get("risk_emoji") or "🚨")
        headline = html_escape(item.get("alert_title") or item.get("keyword") or "글로벌 경제 속보")
        source = html_escape(item.get("source_label") or "뉴스")
        published = html_escape(item.get("published") or "")
        impact = html_escape(item.get("market_impact") or "글로벌 시장 영향 확인 필요")
        original_title = str(item.get("original_title") or "").strip()

        lines.append(f"\n<b>{idx}. {emoji} [{risk_label}] {headline}</b>")
        meta = f"출처: <b>{source}</b>"
        if published:
            meta += f" / 시각: {published}"
        lines.append(meta)
        lines.append(f"핵심영향: {impact}")
        if original_title and original_title != item.get("alert_title"):
            lines.append(f"원문제목: {html_escape(original_title[:160])}")
        lines.append("근거자료:")
        lines.append(_news_links_html(item.get("news") or [], limit=1))



def _daily_digest_to_telegram_text(
    items: list[dict],
    allowed_categories: list[str],
    hot_issue_count: int,
    card_news_count: int,
    article_count: int,
    lookback_hours: int = 24,
    fallback_info: list[dict] | None = None,
    special_issue_items: list[dict] | None = None,
    special_issue_title: str = "📌 별도 추적 이슈",
    global_breaking_news_items: list[dict] | None = None,
    global_breaking_news_title: str = "🚨 글로벌 속보 TOP 3",
    global_breaking_news_lookback_hours: int = 24,
    global_macro_alert_items: list[dict] | None = None,
    global_macro_alert_title: str = "🌍 글로벌 경제 위험 알림",
) -> str:
    """최종 운영용 텔레그램 리포트입니다.

    구성:
    1) 오늘의 핫이슈: 전체 후보를 조회수 많은 순으로 정리
    2) 글로벌 속보 TOP 3: 경제 영향 가능 글로벌 기사/SNS 게시물 최신 발행순
    3) 글로벌 경제 위험 알림: 전쟁/질병/환율/원자재/금리/루머/Reuters/Bloomberg성 속보
    4) 별도 추적 이슈: 사용자가 지정한 고정 추적 주제
    5) 오늘의 카드뉴스: 카드뉴스 제작 추천 항목
    6) 오늘의 작성글: 블로그/워드프레스 작성 추천 항목
    """
    evidence_items_count = sum(1 for item in items if len(item.get("news") or []) > 0)
    lines = [
        "🔥 <b>오늘의 핫이슈 · 카드뉴스 · 작성글 후보</b>",
        f"분야 필터: <b>{html_escape(_allowed_label(allowed_categories))}</b>",
        f"수집 기준: <b>최근 {int(lookback_hours)}시간 이내</b>",
        "정렬 기준: <b>종합 관심도 순</b> = Google Trends 조회수 + 네이버 뉴스량 + 네이버 DataLab 상대지수",
        f"근거자료 포함: <b>{evidence_items_count}/{len(items)}</b>개 항목",
        "근거자료는 <b>네이버 뉴스 우선</b>, 부족하면 Google News로 보완합니다.",
        "기사 URL은 길게 노출하지 않고 <b>링크1~링크5</b> 라벨로 표시합니다.",
    ]

    if fallback_info:
        lines.append("\n🔎 <b>자동 대체 검색 로그</b>")
        for idx, stage in enumerate(fallback_info, 1):
            label = html_escape(stage.get("label", ""))
            item_count = int(stage.get("item_count", 0) or 0)
            evidence_count = int(stage.get("evidence_count", 0) or 0)
            used = " → <b>사용</b>" if stage.get("used") else ""
            lines.append(f"{idx}) {label}: 후보 {item_count}개 / 근거 포함 {evidence_count}개{used}")

    if not items:
        lines.append("\n수집된 작성 후보가 없습니다. 카테고리 필터 또는 선택 주제를 확인해주세요.")
        _append_global_breaking_news_section(lines, global_breaking_news_items, global_breaking_news_title, global_breaking_news_lookback_hours)
        _append_global_macro_alert_section(lines, global_macro_alert_items, global_macro_alert_title)
        if special_issue_items:
            lines.append("\n{}".format(f"<b>{html_escape(special_issue_title)}</b>"))
            for idx, item in enumerate(special_issue_items, 1):
                keyword = html_escape(item.get("keyword") or "")
                category = html_escape(item.get("category_label") or "")
                interest = html_escape(item.get("interest_label") or _interest_label(item.get("composite_score")))
                evidence = html_escape(item.get("evidence_strength") or "")
                angle = html_escape(item.get("angle") or "")
                lines.append(f"\n<b>{idx}. [{category}] {keyword}</b>")
                lines.append(f"관심도: <b>{interest}</b> / 근거강도: {evidence}")
                if angle:
                    lines.append(f"작성각도: {angle}")
                lines.append("근거자료:")
                lines.append(_news_links_html(item.get("news") or []))
        return "\n".join(lines)

    ranked_items = sorted(items, key=_rank_sort_key, reverse=True)
    hot_items = ranked_items[: max(0, hot_issue_count)]
    card_items = _select_card_news_items(hot_items, card_news_count)
    article_items = _select_article_items(hot_items, article_count)

    lines.append("\n🔥 <b>오늘의 핫이슈 TOP {}</b>".format(len(hot_items)))
    for idx, item in enumerate(hot_items, 1):
        keyword = html_escape(item.get("keyword") or "")
        category = html_escape(item.get("category_label") or "")
        traffic = html_escape(item.get("traffic_label") or _traffic_label(item.get("approx_traffic")))
        interest = html_escape(item.get("interest_label") or _interest_label(item.get("composite_score")))
        naver_news_count = _to_int(item.get("naver_news_count", 0))
        datalab_score = float(item.get("naver_datalab_score", 0) or 0)
        source = html_escape(item.get("source") or "")
        evidence = html_escape(item.get("evidence_strength") or "")
        angle = html_escape(item.get("angle") or "")
        lines.append(f"\n<b>{idx}. [{category}] {keyword}</b>")
        lines.append(f"관심도: <b>{interest}</b> / Google 조회수: <b>{traffic}</b> / 근거강도: {evidence}")
        if naver_news_count or datalab_score:
            lines.append(f"네이버 신호: 최근뉴스 {naver_news_count}건 / DataLab {datalab_score:.1f}")
        if source:
            lines.append(f"수집경로: {source}")
        if angle:
            lines.append(f"작성각도: {angle}")
        lines.append("근거자료:")
        lines.append(_news_links_html(item.get("news") or []))

    _append_global_breaking_news_section(lines, global_breaking_news_items, global_breaking_news_title, global_breaking_news_lookback_hours)
    _append_global_macro_alert_section(lines, global_macro_alert_items, global_macro_alert_title)

    if special_issue_items:
        lines.append("\n{}".format(f"<b>{html_escape(special_issue_title)}</b>"))
        for idx, item in enumerate(special_issue_items, 1):
            keyword = html_escape(item.get("keyword") or "")
            category = html_escape(item.get("category_label") or "")
            interest = html_escape(item.get("interest_label") or _interest_label(item.get("composite_score")))
            naver_news_count = _to_int(item.get("naver_news_count", 0))
            datalab_score = float(item.get("naver_datalab_score", 0) or 0)
            evidence = html_escape(item.get("evidence_strength") or "")
            angle = html_escape(item.get("angle") or "")
            lines.append(f"\n<b>{idx}. [{category}] {keyword}</b>")
            lines.append(f"관심도: <b>{interest}</b> / 근거강도: {evidence}")
            if naver_news_count or datalab_score:
                lines.append(f"네이버 신호: 최근뉴스 {naver_news_count}건 / DataLab {datalab_score:.1f}")
            if angle:
                lines.append(f"작성각도: {angle}")
            lines.append("근거자료:")
            lines.append(_news_links_html(item.get("news") or []))

    lines.append("\n🃏 <b>오늘의 카드뉴스 추천</b>")
    if not card_items:
        lines.append("추천 항목이 없습니다.")
    for idx, item in enumerate(card_items, 1):
        keyword = html_escape(item.get("keyword") or "")
        ref_rank = hot_items.index(item) + 1 if item in hot_items else item.get("rank", "-")
        traffic = html_escape(item.get("traffic_label") or _traffic_label(item.get("approx_traffic")))
        angle = html_escape(item.get("card_news_angle") or "")
        lines.append(f"\n<b>{idx}. #{ref_rank} {keyword}</b>")
        lines.append(f"선정이유: 관심도 {html_escape(item.get('interest_label') or _interest_label(item.get('composite_score')))}, Google 조회수 {traffic}, 기사근거 {len(item.get('news') or [])}개")
        lines.append(f"구성방향: {angle}")

    lines.append("\n✍️ <b>오늘의 작성글 추천</b>")
    if not article_items:
        lines.append("추천 항목이 없습니다.")
    for idx, item in enumerate(article_items, 1):
        keyword = html_escape(item.get("keyword") or "")
        ref_rank = hot_items.index(item) + 1 if item in hot_items else item.get("rank", "-")
        traffic = html_escape(item.get("traffic_label") or _traffic_label(item.get("approx_traffic")))
        angle = html_escape(item.get("article_angle") or "")
        lines.append(f"\n<b>{idx}. #{ref_rank} {keyword}</b>")
        lines.append(f"선정이유: 검색 유입 가능성 + 관심도 {html_escape(item.get('interest_label') or _interest_label(item.get('composite_score')))} + 근거 기사 {len(item.get('news') or [])}개")
        lines.append(f"글방향: {angle}")

    lines.append("\n📌 <b>운영 메모</b>")
    lines.append(f"Google Trends approx traffic은 조회수 참고값으로 사용하고, 네이버 뉴스량/DataLab 상대지수로 순위를 보정합니다.")
    lines.append(f"근거자료는 네이버 뉴스 검색 API를 우선 사용하고 부족하면 Google News RSS 최근 {int(lookback_hours)}시간 기준으로 보완합니다.")
    lines.append("seed 키워드는 기본 제외됩니다. 필요할 때만 include_seed_keywords=true로 켜세요.")
    return "\n".join(lines)



def _ideas_to_telegram_text(items: list[dict], allowed_categories: list[str]) -> str:
    """이전 버전 호환용: 이제 일일 운영 리포트 형식으로 전달합니다."""
    return _daily_digest_to_telegram_text(
        items,
        allowed_categories,
        _safe_int_env("HOT_ISSUE_COUNT", 10),
        _safe_int_env("CARD_NEWS_COUNT", 3),
        _safe_int_env("ARTICLE_COUNT", 3),
        _safe_int_env("LOOKBACK_HOURS", 24),
    )



def _build_special_issue_items(
    topics: list[str],
    geo: str,
    links_per_topic: int,
    lookback_hours: int,
    category_filter: str = "all",
    max_items: int = 5,
) -> list[dict]:
    """오늘의 핫이슈와 별개로 사용자가 지정한 추적 이슈를 구성합니다.

    SPECIAL_ISSUES에 지정한 주제는 트렌드 순위 후보와 섞지 않고 별도 섹션으로만 표시합니다.
    """
    if not topics:
        return []

    allowed_categories = _parse_category_filter(category_filter or "all")
    manual_keywords = _keyword_dataframe_from_topics(topics)
    prepared = _prepare_keywords_with_categories(manual_keywords, allowed_categories)

    # 지정 주제가 카테고리 필터 때문에 모두 빠지면, 사용자가 의도한 추적 주제를 살리기 위해 전체 카테고리로 재시도합니다.
    if prepared.empty and allowed_categories != list(CATEGORY_GROUPS.keys()):
        prepared = _prepare_keywords_with_categories(manual_keywords, list(CATEGORY_GROUPS.keys()))

    items = _build_idea_digest(
        prepared,
        max_items=max(1, int(max_items or 5)),
        links_per_topic=links_per_topic,
        geo=geo,
        lookback_hours=lookback_hours,
    )
    return sorted(items, key=_rank_sort_key, reverse=True)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--geo", default=os.environ.get("GOOGLE_TRENDS_GEO", "KR"))
    parser.add_argument("--max-keywords", type=int, default=int(os.environ.get("MAX_KEYWORDS", "30")))
    parser.add_argument("--max-posts", type=int, default=int(os.environ.get("MAX_POSTS_PER_RUN", "10")))
    parser.add_argument("--topics", default=os.environ.get("SELECTED_TOPICS", ""))
    parser.add_argument("--category-filter", default=os.environ.get("CATEGORY_FILTER", "finance"))
    parser.add_argument("--lookback-hours", type=int, default=int(os.environ.get("LOOKBACK_HOURS", "24")))
    parser.add_argument("--include-seed-keywords", action="store_true")
    parser.add_argument("--no-wordpress", action="store_true")
    parser.add_argument("--send-articles-to-telegram", action="store_true")
    parser.add_argument("--list-only", action="store_true", help="글 초안 생성 없이 작성 후보와 관련 기사 링크만 텔레그램으로 전송")
    args = parser.parse_args()

    # 운영 기본값: GitHub Actions 워크플로우가 아직 예전 값(10/3)을 넘기더라도
    # 요청한 운영 기준인 30개 키워드 / 10개 포스팅으로 보정합니다.
    # 더 작은 값으로 테스트하고 싶을 때만 ALLOW_SMALLER_LIMITS=true를 사용하세요.
    if not _env_true("ALLOW_SMALLER_LIMITS"):
        args.max_keywords = max(args.max_keywords, 30)
        args.max_posts = max(args.max_posts, 10)

    telegram_only = _env_true("TELEGRAM_ONLY") or args.no_wordpress
    send_articles_to_telegram = (
        _env_true("SEND_ARTICLES_TO_TELEGRAM")
        or args.send_articles_to_telegram
        or telegram_only
    )
    # 기본 운영은 "후보 리스트만 전송"입니다. 글 초안 생성/워드프레스 업로드는 필요할 때만 끕니다.
    list_only = _env_true("ITEM_LIST_ONLY", "true") or args.list_only
    links_per_topic = max(1, _safe_int_env("NEWS_LINKS_PER_TOPIC", 5))
    hot_issue_count = max(1, _safe_int_env("HOT_ISSUE_COUNT", args.max_posts))
    card_news_count = max(0, _safe_int_env("CARD_NEWS_COUNT", 3))
    article_count = max(0, _safe_int_env("ARTICLE_COUNT", 3))
    special_issue_topics = _parse_topics(os.environ.get("SPECIAL_ISSUES", ""))
    special_issue_title = os.environ.get("SPECIAL_ISSUE_TITLE", "📌 별도 추적 이슈").strip() or "📌 별도 추적 이슈"
    special_issue_count = max(1, _safe_int_env("SPECIAL_ISSUE_COUNT", 5))
    special_issue_category_filter = os.environ.get("SPECIAL_ISSUE_CATEGORY_FILTER", "all")
    global_macro_alert_enabled = _env_true("GLOBAL_MACRO_ALERT_ENABLED", "true")
    global_macro_alert_title = os.environ.get("GLOBAL_MACRO_ALERT_TITLE", "🌍 글로벌 경제 위험 알림").strip() or "🌍 글로벌 경제 위험 알림"
    global_macro_alert_topics = _global_macro_topics_from_env(os.environ.get("GLOBAL_MACRO_ALERT_TOPICS", ""))
    global_macro_alert_count = max(1, _safe_int_env("GLOBAL_MACRO_ALERT_COUNT", 7))
    global_macro_alert_lookback_hours = max(1, _safe_int_env("GLOBAL_MACRO_ALERT_LOOKBACK_HOURS", _safe_int_env("LOOKBACK_HOURS", args.lookback_hours)))
    global_breaking_news_enabled = _env_true("GLOBAL_BREAKING_NEWS_ENABLED", "true")
    global_breaking_news_title = os.environ.get("GLOBAL_BREAKING_NEWS_TITLE", "🚨 글로벌 속보 TOP 3").strip() or "🚨 글로벌 속보 TOP 3"
    global_breaking_news_count = max(1, _safe_int_env("GLOBAL_BREAKING_NEWS_COUNT", 3))
    global_breaking_news_lookback_hours = max(1, _safe_int_env("GLOBAL_BREAKING_NEWS_LOOKBACK_HOURS", _safe_int_env("LOOKBACK_HOURS", args.lookback_hours)))
    global_breaking_news_use_direct_sites = _env_true("GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES", "true")
    global_breaking_news_queries = _parse_topics(os.environ.get("GLOBAL_BREAKING_NEWS_QUERIES", ""))
    global_breaking_social_feeds = os.environ.get("GLOBAL_BREAKING_SOCIAL_FEEDS", "")
    allowed_categories = _parse_category_filter(args.category_filter)
    include_seed_keywords = _env_true("INCLUDE_SEED_KEYWORDS", "false") or args.include_seed_keywords
    auto_fallback = _env_true("AUTO_FALLBACK", "true")
    fallback_lookback_hours = _safe_int_env("FALLBACK_LOOKBACK_HOURS", 48)

    topics = _parse_topics(args.topics)

    Path("reports").mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    # list_only 모드에서는 후보/근거가 부족할 때 자동 대체 검색을 수행합니다.
    # 글 초안 생성 모드에서는 기존처럼 요청 필터만 사용합니다.
    if list_only:
        digest_item_count = max(args.max_posts, hot_issue_count, card_news_count, article_count)
        items, raw_keywords, keywords, effective_categories, effective_lookback_hours, fallback_info = _build_idea_digest_with_fallback(
            args=args,
            topics=topics,
            initial_categories=allowed_categories,
            include_seed_keywords=include_seed_keywords,
            max_items=digest_item_count,
            links_per_topic=links_per_topic,
            base_lookback_hours=args.lookback_hours,
            auto_fallback=auto_fallback,
            fallback_lookback_hours=fallback_lookback_hours,
        )
        raw_keywords.to_csv(f"reports/trend_keywords_raw_{today}.csv", index=False, encoding="utf-8-sig")
        keywords.to_csv(f"reports/trend_keywords_{today}.csv", index=False, encoding="utf-8-sig")
        Path(f"reports/idea_items_{today}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        special_issue_items = _build_special_issue_items(
            topics=special_issue_topics,
            geo=args.geo,
            links_per_topic=links_per_topic,
            lookback_hours=effective_lookback_hours,
            category_filter=special_issue_category_filter,
            max_items=special_issue_count,
        )
        if special_issue_items:
            Path(f"reports/special_issue_items_{today}.json").write_text(
                json.dumps(special_issue_items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        global_breaking_news_items = []
        if global_breaking_news_enabled:
            global_breaking_news_items = fetch_global_breaking_news(
                limit=global_breaking_news_count,
                geo=args.geo,
                lookback_hours=global_breaking_news_lookback_hours,
                queries=global_breaking_news_queries or None,
                use_direct_sites=global_breaking_news_use_direct_sites,
                social_feeds=global_breaking_social_feeds,
            )
            if global_breaking_news_items:
                Path(f"reports/global_breaking_news_{today}.json").write_text(
                    json.dumps(global_breaking_news_items, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        global_macro_alert_items = _build_global_macro_alert_items(
            enabled=global_macro_alert_enabled,
            topics=global_macro_alert_topics,
            geo=args.geo,
            links_per_topic=links_per_topic,
            lookback_hours=global_macro_alert_lookback_hours,
            max_items=global_macro_alert_count,
        )
        if global_macro_alert_items:
            Path(f"reports/global_macro_alert_items_{today}.json").write_text(
                json.dumps(global_macro_alert_items, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        flat_rows = []
        card_keywords = {item.get("keyword") for item in _select_card_news_items(items[:hot_issue_count], card_news_count)}
        article_keywords = {item.get("keyword") for item in _select_article_items(items[:hot_issue_count], article_count)}
        for rank, item in enumerate(items, 1):
            news = item.get("news") or []
            uses = []
            if rank <= hot_issue_count:
                uses.append("오늘의 핫이슈")
            if item.get("keyword") in card_keywords:
                uses.append("오늘의 카드뉴스")
            if item.get("keyword") in article_keywords:
                uses.append("오늘의 작성글")
            flat_rows.append({
                "rank": rank,
                "keyword": item.get("keyword", ""),
                "category": item.get("category_label", ""),
                "approx_traffic": item.get("approx_traffic", 0),
                "traffic_label": item.get("traffic_label", ""),
                "composite_score": item.get("composite_score", 0),
                "interest_label": item.get("interest_label", ""),
                "naver_news_count": item.get("naver_news_count", 0),
                "naver_datalab_score": item.get("naver_datalab_score", 0),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
                "age_hours": item.get("age_hours", ""),
                "recommended_use": " / ".join(uses),
                "angle": item.get("angle", ""),
                "evidence_strength": item.get("evidence_strength", ""),
                "news_count": len(news),
                "news_links": " | ".join(n.get("url", "") for n in news),
            })
        pd.DataFrame(flat_rows).to_csv(f"reports/idea_items_{today}.csv", index=False, encoding="utf-8-sig")
        send_telegram_long(
            _daily_digest_to_telegram_text(
                items,
                effective_categories,
                hot_issue_count,
                card_news_count,
                article_count,
                effective_lookback_hours,
                fallback_info=fallback_info,
                special_issue_items=special_issue_items,
                special_issue_title=special_issue_title,
                global_breaking_news_items=global_breaking_news_items,
                global_breaking_news_title=global_breaking_news_title,
                global_breaking_news_lookback_hours=global_breaking_news_lookback_hours,
                global_macro_alert_items=global_macro_alert_items,
                global_macro_alert_title=global_macro_alert_title,
            ),
            parse_mode="HTML",
        )
        return

    raw_keywords, keywords = _collect_keywords_for_stage(
        args,
        topics,
        allowed_categories,
        include_seed_keywords,
        args.lookback_hours,
    )
    raw_keywords.to_csv(f"reports/trend_keywords_raw_{today}.csv", index=False, encoding="utf-8-sig")
    keywords.to_csv(f"reports/trend_keywords_{today}.csv", index=False, encoding="utf-8-sig")

    results = []
    for _, row in keywords.head(args.max_posts).iterrows():
        keyword = row["keyword"]
        category_id = row.get("category_id") or _classify_keyword(keyword)
        article = None
        try:
            article = generate_article(keyword, os.environ.get("SITE_DESCRIPTION", "생활 정보 블로그"))
            article["category_id"] = category_id
            article["category_label"] = _category_short_label(category_id)
            Path(f"reports/article_{today}_{len(results) + 1}.json").write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            wp_result = {}
            if not telegram_only:
                wp_result = create_wp_post(article, status=os.environ.get("WP_DEFAULT_STATUS", "draft"))

            results.append({
                "keyword": keyword,
                "category": _category_short_label(category_id),
                "title": article.get("title"),
                "status": "telegram_only" if telegram_only else "draft",
                "wp_link": wp_result.get("link", ""),
                "review_checklist": " | ".join(article.get("review_checklist", [])),
            })

            if send_articles_to_telegram:
                send_telegram_long(_article_to_plain_text(article), parse_mode=None)

        except Exception as exc:
            print(f"[ERROR] {keyword}: {exc}")
            item = {"keyword": keyword, "category": _category_short_label(category_id), "error": _short_error(exc)}
            if article:
                item["title"] = article.get("title")
                item["status"] = "generated_wp_failed"
                # WordPress 업로드만 실패해도 생성된 글은 텔레그램으로 확인할 수 있게 보냅니다.
                if send_articles_to_telegram or _env_true("SEND_ARTICLE_ON_WP_FAIL", "true"):
                    send_telegram_long(_article_to_plain_text(article), parse_mode=None)
            results.append(item)

    pd.DataFrame(results).to_csv(f"reports/generated_posts_{today}.csv", index=False, encoding="utf-8-sig")

    lines = ["📝 <b>AdSense SEO 초안 생성 리포트</b>"]
    lines.append(f"분야 필터: <b>{html_escape(', '.join(_category_short_label(c) for c in allowed_categories))}</b>")
    if telegram_only:
        lines.append("모드: 텔레그램 전용 생성 / WordPress 업로드 생략")
    elif topics:
        lines.append("모드: 선택 주제 생성")

    if not results:
        lines.append("생성할 수 있는 키워드가 없습니다. 선택 주제 또는 카테고리 필터를 확인해주세요.")

    for i, r in enumerate(results, 1):
        category = html_escape(r.get("category") or "")
        if r.get("error"):
            title = r.get("title")
            title_line = f"\n생성제목: {html_escape(title)}" if title else ""
            lines.append(f"{i}. ❌ [{category}] {html_escape(r['keyword'])}{title_line}\n오류: {html_escape(r['error'])}")
        else:
            title = html_escape(r.get("title") or "제목 없음")
            keyword = html_escape(r.get("keyword") or "")
            link = html_escape(r.get("wp_link") or "텔레그램 전송 완료" if telegram_only else "(로컬 저장)")
            lines.append(f"{i}. ✅ [{category}] <b>{title}</b>\n키워드: {keyword}\n{link}")

    send_telegram("\n\n".join(lines), parse_mode="HTML")


if __name__ == "__main__":
    main()
