# AdSense SEO 자동화 스타터 v11

트렌드 키워드를 수집하고, 텔레그램으로 **오늘의 핫이슈 / 오늘의 카드뉴스 / 오늘의 작성글 후보**를 보내는 자동화 패키지입니다.

## v11 핵심 변경

- 기존 Google 기반 수집에 **Naver Search API 뉴스 검색**을 추가했습니다.
- 근거 기사 링크는 기본적으로 **네이버 뉴스 우선**으로 가져오고, 부족한 경우 Google News RSS로 보완합니다.
- 네이버 뉴스 최신 제목을 후보 아이템으로 보강할 수 있습니다.
- 네이버 DataLab 통합검색어 트렌드 상대지수를 순위 보정에 사용합니다.
- 최종 정렬은 단순 Google 조회수만이 아니라 아래 기준을 합산한 **종합 관심도 순**입니다.
  - Google Trends RSS approx traffic
  - 최근 네이버 뉴스 기사 수
  - 네이버 DataLab 상대 검색지수
  - 근거 기사 수 및 내부 점수

> 참고: 네이버 Open API는 개별 검색어의 절대 조회수나 기사 조회수를 제공하지 않습니다. 그래서 v11의 `관심도`는 실제 조회수 원문이 아니라 Google Trends 조회수 참고값 + 네이버 뉴스량 + DataLab 상대지수를 합산한 운영용 점수입니다.

## 필요한 GitHub Secrets

기존 값에 아래 2개를 추가하면 네이버 기반 보강이 활성화됩니다.

```text
NAVER_CLIENT_ID
NAVER_CLIENT_SECRET
```

기존 필수 값은 다음과 같습니다.

```text
GEMINI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
WP_SITE_URL
WP_USERNAME
WP_APP_PASSWORD
```

`ITEM_LIST_ONLY=true`로 후보 리포트만 받을 경우 WordPress 관련 값은 당장 사용되지 않습니다.

## 기본 실행값

```text
MAX_KEYWORDS=30
MAX_POSTS_PER_RUN=10
ITEM_LIST_ONLY=true
NEWS_LINKS_PER_TOPIC=5
LOOKBACK_HOURS=24
AUTO_FALLBACK=true
FALLBACK_LOOKBACK_HOURS=48
INCLUDE_SEED_KEYWORDS=false
HOT_ISSUE_COUNT=10
CARD_NEWS_COUNT=3
ARTICLE_COUNT=3
CATEGORY_FILTER=finance
NEWS_PROVIDER=naver_first
USE_NAVER_NEWS_CANDIDATES=true
USE_NAVER_DATALAB=true
```

## 자동 확장 로직

기본은 **경제·금융 + 최근 24시간**입니다. 후보가 없거나 근거자료가 부족하면 자동으로 확장합니다.

1. `finance + 최근 24시간`
2. `all + 최근 24시간`
3. `all + 최근 48시간`

텔레그램 상단의 `자동 대체 검색 로그`에서 실제 사용된 단계를 확인할 수 있습니다.

## 텔레그램 표시 예시

```text
🔥 오늘의 핫이슈 · 카드뉴스 · 작성글 후보
분야 필터: 경제·금융 우선
수집 기준: 최근 24시간 이내
정렬 기준: 종합 관심도 순 = Google Trends 조회수 + 네이버 뉴스량 + 네이버 DataLab 상대지수
근거자료 포함: 8/10개 항목
근거자료는 네이버 뉴스 우선, 부족하면 Google News로 보완합니다.

🔥 오늘의 핫이슈 TOP 10

1. [경제·금융] 기준금리 전망
관심도: 148,000점 / Google 조회수: 10.0만+ / 근거강도: 강함
네이버 신호: 최근뉴스 6건 / DataLab 72.5
수집경로: google_trends_rss_24h
작성각도: 금리 변화 → 가계부담/저축전략 → 확인할 금융상품 포인트
근거자료:
  1) 기사 제목 (언론사 · 06-26 08:31) / 링크1
  2) 기사 제목 (언론사 · 06-26 08:12) / 링크2
```


## 자동 실행 일정

GitHub Actions는 UTC 기준으로 동작하므로, 한국시간 기준 아래 4회 실행되도록 설정했습니다.

| 한국시간(KST) | UTC cron 실행 시간 | 용도 예시 |
|---|---:|---|
| 오전 6시 | 전일 21:00 UTC | 출근 전 새벽/오전 이슈 확인 |
| 오전 11시 | 02:00 UTC | 오전장·오전 뉴스 반영 |
| 오후 3시 | 06:00 UTC | 장중/오후 이슈 반영 |
| 오후 7시 | 10:00 UTC | 저녁 주요 이슈 정리 |

워크플로우 설정값:

```yaml
schedule:
  - cron: "0 2,6,10,21 * * *"
```

## GitHub Actions 수동 실행 옵션

`Actions → daily-adsense-seo → Run workflow`에서 아래 값을 조정할 수 있습니다.

| 옵션 | 기본값 | 설명 |
|---|---:|---|
| `topics` | 비움 | 특정 주제만 보고 싶을 때 쉼표/줄바꿈으로 입력 |
| `category_filter` | `finance` | 경제·금융 우선. `all`이면 전체 카테고리 |
| `news_provider` | `naver_first` | 네이버 뉴스 우선. `google`이면 Google News만 사용 |
| `use_naver_news_candidates` | `true` | 네이버 뉴스 최신 제목을 후보 아이템으로 보강 |
| `use_naver_datalab` | `true` | 네이버 DataLab 상대지수로 순위 보정 |
| `item_list_only` | `true` | 글 초안 생성 없이 후보 리포트만 전송 |
| `news_links_per_topic` | `5` | 주제별 근거 기사 링크 수 |
| `lookback_hours` | `24` | 최근 자료 기준 시간 |
| `auto_fallback` | `true` | 후보/근거가 부족하면 전체 카테고리와 48시간으로 자동 확장 |
| `fallback_lookback_hours` | `48` | 자동 확장 시 최종 시간 범위 |
| `include_seed_keywords` | `false` | seed 키워드 포함 여부. 최신 운영에서는 false 권장 |
| `hot_issue_count` | `10` | 오늘의 핫이슈 표시 개수 |
| `card_news_count` | `3` | 오늘의 카드뉴스 추천 개수 |
| `article_count` | `3` | 오늘의 작성글 추천 개수 |
| `telegram_only` | `false` | 글 초안 생성 모드에서 WordPress 업로드 생략 |
| `send_articles_to_telegram` | `false` | 글 초안 생성 모드에서 본문을 텔레그램으로 전송 |

## 카테고리 필터

기본값 `finance`에는 아래 4개 그룹이 포함됩니다.

- `💰 경제·금융`: 금리, 환율, 물가, 대출, 예금, 카드, 보험, 세금
- `📈 증권·투자`: 코스피, 코스닥, 주식, ETF, 공모주, 실적, 반도체
- `🏠 부동산·주거금융`: 청약, 전세, 월세, 주택담보대출, DSR
- `🏛️ 정책·지원금`: 소상공인 지원금, 근로장려금, 국민연금, 최저임금

전체 카테고리를 보고 싶으면 수동 실행에서 `category_filter=all`로 바꾸면 됩니다.

## 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py --max-keywords 30 --max-posts 10 --category-filter finance --lookback-hours 24
```

## 보고서 파일

실행이 끝나면 GitHub Actions artifact로 아래 파일이 저장됩니다.

- `trend_keywords_raw_YYYYMMDD.csv`: 원본 수집 키워드
- `trend_keywords_YYYYMMDD.csv`: 카테고리 필터 후 키워드
- `idea_items_YYYYMMDD.json`: 후보 아이템과 근거 기사 전체 데이터
- `idea_items_YYYYMMDD.csv`: 순위, 관심도, 네이버 신호, 추천 용도, 근거 기사 링크 요약
