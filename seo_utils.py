import re
try:
    from slugify import slugify
except Exception:
    def slugify(text, lowercase=True, max_length=80):
        text = str(text or "")
        text = re.sub(r"[^A-Za-z0-9가-힣]+", "-", text).strip("-")
        if lowercase:
            text = text.lower()
        return text[:max_length].strip("-")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def make_slug(text: str) -> str:
    return slugify(text, lowercase=True, max_length=80) or "post"


def is_blocked_keyword(keyword: str, blocked_csv: str = "") -> bool:
    kw = clean_text(keyword).lower()
    blocked = [clean_text(x).lower() for x in (blocked_csv or "").split(",") if clean_text(x)]
    return any(b and b in kw for b in blocked)


def is_valid_korean_keyword(keyword: str, allow_english: bool = False) -> bool:
    """한국어 블로그 자동화에 맞지 않는 해외 트렌드 키워드를 제외합니다.

    - 기본값: 한글이 포함된 키워드만 허용
    - 일본어 가나/한자만 있는 키워드, 중국어만 있는 키워드, 인도네시아어 등
      외국어 키워드가 채널에 섞이는 문제를 방지합니다.
    - 영어 이슈 키워드를 허용하고 싶으면 환경변수 ALLOW_ENGLISH_KEYWORDS=true를 사용합니다.
    """
    text = clean_text(keyword)
    if not text:
        return False

    if re.search(r"[가-힣]", text):
        return True

    if allow_english and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s&+./#:'\-]{1,80}", text):
        return True

    return False


def score_keyword(keyword: str, source: str = "", approx_traffic: int = 0) -> float:
    score = 50.0
    if approx_traffic:
        score += min(30, approx_traffic / 10000)
    if len(keyword) >= 4:
        score += 5
    if any(x in keyword for x in ["방법", "정리", "뜻", "신청", "비교", "추천", "기간", "가격"]):
        score += 10
    return round(min(score, 100), 2)
