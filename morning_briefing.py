GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

WP_SITE_URL=https://gooddaynews.store
# WP_API_URL은 보통 비워두세요. REST 주소를 직접 지정해야 할 때만 사용합니다.
# WP_API_URL=https://gooddaynews.store/wp-json/wp/v2/posts
WP_USERNAME=your_wordpress_username
WP_APP_PASSWORD=your_wordpress_application_password
WP_DEFAULT_STATUS=draft

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=@your_channel_username_or_-100_id

SITE_DESCRIPTION=생활 정보와 뉴스 이슈를 쉽게 정리하는 블로그
GOOGLE_TRENDS_GEO=KR
MAX_KEYWORDS=30
MAX_POSTS_PER_RUN=10
# true면 글 초안/워드프레스 업로드 없이 작성 후보 아이템과 관련 기사 링크만 보냅니다.
ITEM_LIST_ONLY=true
# 주제별 관련 신문 기사 링크 수
NEWS_LINKS_PER_TOPIC=5
# 오늘의 핫이슈/카드뉴스/작성글 추천 개수
HOT_ISSUE_COUNT=10
CARD_NEWS_COUNT=3
ARTICLE_COUNT=3

# 오늘의 핫이슈와 별개로 항상 추적할 이슈
# 예: 국민연금 환율, 코스피 8000, 전기요금 동결
SPECIAL_ISSUES=
SPECIAL_ISSUE_TITLE=📌 별도 추적 이슈
SPECIAL_ISSUE_COUNT=5
SPECIAL_ISSUE_CATEGORY_FILTER=all

# 글로벌 경제 위험 알림: 전쟁/질병/환율/원자재/금리/루머/로이터·블룸버그성 속보
GLOBAL_MACRO_ALERT_ENABLED=true
GLOBAL_MACRO_ALERT_TITLE=🌍 글로벌 경제 위험 알림
# 비워두면 코드의 기본 묶음을 사용합니다. 직접 운영하려면 쉼표/줄바꿈으로 입력하세요.
# 예: 로이터 속보 글로벌 경제 시장, 블룸버그 속보 글로벌 시장 경제, 원달러 환율 급등 급락, 국제유가 급등 급락
GLOBAL_MACRO_ALERT_TOPICS=
GLOBAL_MACRO_ALERT_COUNT=7
GLOBAL_MACRO_ALERT_LOOKBACK_HOURS=24

# 글로벌 속보 TOP 3: 경제 영향 가능 글로벌 기사/SNS 게시물을 최신 발행순으로 별도 전송
GLOBAL_BREAKING_NEWS_ENABLED=true
GLOBAL_BREAKING_NEWS_TITLE=🚨 글로벌 속보 TOP 3
GLOBAL_BREAKING_NEWS_COUNT=3
GLOBAL_BREAKING_NEWS_LOOKBACK_HOURS=24
# true면 Google News RSS 외에 AP/BBC/CNBC/Fed/WHO 등 실제 뉴스/공식 RSS 후보도 보조 확인합니다.
GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES=true
# 비워두면 Reuters/Bloomberg/시장 속보 기본 묶음을 사용합니다.
GLOBAL_BREAKING_NEWS_QUERIES=
# 영향력 인물 SNS 글을 RSS/Atom으로 받을 수 있는 feed가 있으면 이름|URL 형식으로 추가합니다.
# 예: Elon Musk|https://example.com/elon/rss, Fed Chair|https://example.com/powell/rss
GLOBAL_BREAKING_SOCIAL_FEEDS=

# 카테고리 필터
# finance: 경제·금융/증권·투자/부동산·주거금융/정책·지원금만 사용
# all: 전체 카테고리 사용
# economy_finance,stock_investment 처럼 쉼표로 직접 지정 가능
CATEGORY_FILTER=finance

# 수동으로 특정 주제만 생성하고 싶을 때 쉼표/줄바꿈으로 입력합니다.
SELECTED_TOPICS=
# true면 WordPress 업로드 없이 텔레그램으로만 글 초안을 보냅니다.
TELEGRAM_ONLY=false
# true면 WordPress 업로드 성공 여부와 관계없이 생성된 글 본문을 텔레그램으로 별도 전송합니다.
SEND_ARTICLES_TO_TELEGRAM=false
# WordPress 업로드 실패 시에도 생성된 글 본문을 텔레그램으로 전송합니다.
SEND_ARTICLE_ON_WP_FAIL=true
ALLOW_ENGLISH_KEYWORDS=false
ALLOW_SMALLER_LIMITS=false

# 최근 자료 기준 시간
LOOKBACK_HOURS=24
# 후보/근거자료가 부족하면 자동으로 전체 카테고리 → 48시간으로 확장
AUTO_FALLBACK=true
FALLBACK_LOOKBACK_HOURS=48
# 최신 트렌드 운영에서는 기본 false 권장
INCLUDE_SEED_KEYWORDS=false

# Naver Open API credentials. 없으면 Google 기반으로 자동 동작합니다.
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
# naver_first: 네이버 뉴스 우선 + 부족분 Google 보완 / google: Google News만 / mixed: 네이버+Google
NEWS_PROVIDER=naver_first
# true면 네이버 뉴스 최신 제목을 후보 아이템으로 보강합니다.
USE_NAVER_NEWS_CANDIDATES=true
# true면 네이버 DataLab 상대 검색지수를 순위 보정에 사용합니다.
USE_NAVER_DATALAB=true


# -----------------------------------------------------------------------------
# 한국 기준 / 48시간 기사 제한 / 날씨 / 인물명 안전장치
# -----------------------------------------------------------------------------
DEFAULT_REGION=KR
DEFAULT_LOCALE=ko-KR
DEFAULT_TIMEZONE=Asia/Seoul

# 근거 기사로 사용할 최대 기사 나이. 기본 48시간.
SUPPORTING_NEWS_MAX_AGE_HOURS=48
# 발행시각을 확인할 수 없는 기사는 근거자료에서 제외.
EXCLUDE_UNKNOWN_PUBLISHED_AT=true

# /topic 오늘 날씨 요청 또는 ALWAYS_INCLUDE_WEATHER=true일 때 사용
WEATHER_ENABLED=true
WEATHER_DEFAULT_CITY=서울
WEATHER_DEFAULT_LAT=37.5665
WEATHER_DEFAULT_LON=126.9780
ALWAYS_INCLUDE_WEATHER=false

# 한국어 인물명 동명이인 방지
PERSON_KEYWORD_GUARD=true
PERSON_KEYWORD_MIN_CONTEXT_MATCH=2
PERSON_KEYWORD_AMBIGUITY_WARNING=true

# Telegram 링크 표시
TELEGRAM_URL_BUTTONS=true
TELEGRAM_LINK_BUTTON_LIMIT=8
