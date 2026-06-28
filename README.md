# AdSense SEO 자동화 스타터 v12

트렌드 키워드를 수집하고, 텔레그램으로 **오늘의 핫이슈 / 글로벌 속보 TOP 3 / 글로벌 경제 위험 알림 / 별도 추적 이슈 / 오늘의 카드뉴스 / 오늘의 작성글 후보**를 보내는 자동화 패키지입니다.

## v12 핵심 변경

- **글로벌 경제 위험 알림**을 추가해 전쟁·질병·환율·원자재·금리·시장루머·Reuters/Bloomberg성 속보를 별도 섹션으로 보냅니다.
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
SPECIAL_ISSUES=
SPECIAL_ISSUE_TITLE=📌 별도 추적 이슈
SPECIAL_ISSUE_COUNT=5
SPECIAL_ISSUE_CATEGORY_FILTER=all
GLOBAL_MACRO_ALERT_ENABLED=true
GLOBAL_MACRO_ALERT_TITLE=🌍 글로벌 경제 위험 알림
GLOBAL_MACRO_ALERT_TOPICS=
GLOBAL_MACRO_ALERT_COUNT=7
GLOBAL_MACRO_ALERT_LOOKBACK_HOURS=24
GLOBAL_BREAKING_NEWS_ENABLED=true
GLOBAL_BREAKING_NEWS_TITLE=🚨 글로벌 속보 TOP 3
GLOBAL_BREAKING_NEWS_COUNT=3
GLOBAL_BREAKING_NEWS_LOOKBACK_HOURS=24
GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES=true
GLOBAL_BREAKING_NEWS_QUERIES=
GLOBAL_BREAKING_SOCIAL_FEEDS=
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

## 별도 추적 이슈 추가

`SPECIAL_ISSUES`에 주제를 넣으면 **오늘의 핫이슈 TOP 10과 섞이지 않고**, 텔레그램 리포트 안에 별도 섹션으로 추가됩니다.

예시:

```text
SPECIAL_ISSUES=국민연금 환율, 코스피 8000, 전기요금 동결
SPECIAL_ISSUE_TITLE=📌 별도 추적 이슈
SPECIAL_ISSUE_COUNT=5
SPECIAL_ISSUE_CATEGORY_FILTER=all
```

자동 예약 실행에서도 유지하려면 GitHub 저장소의 `Settings → Secrets and variables → Actions → Variables`에 같은 이름으로 등록하면 됩니다. 수동 실행에서는 `Run workflow` 입력값으로도 임시 지정할 수 있습니다.

## 글로벌 속보 TOP 3 추가

`GLOBAL_BREAKING_NEWS_ENABLED=true`이면 오늘의 핫이슈와 별도로 **경제 영향 가능성이 있는 글로벌 속보 3개**를 최신 발행순으로 보냅니다.

핵심 차이:

- `오늘의 핫이슈`: 국내 트렌드/관심도 중심
- `🌍 글로벌 경제 위험 알림`: 전쟁·질병·환율·원자재·금리 등 위험 테마별 추적
- `🚨 글로벌 속보 TOP 3`: 경제영향 필터를 통과한 기사/SNS 게시물 중 **가장 최근 발행된 3개만** 별도 표시

기본 수집 방식은 아래 순서입니다.

1. Google News RSS에서 Reuters/Bloomberg/시장 속보성 검색어 확인
2. Google News RSS가 부족할 때 AP/BBC/CNBC/Federal Reserve/WHO 등 실제 뉴스·공식기관 RSS 후보 보조 확인
3. `GLOBAL_BREAKING_SOCIAL_FEEDS`에 사용자가 넣은 SNS/RSS/Atom feed가 있으면 함께 확인

설정 예시:

```text
GLOBAL_BREAKING_NEWS_ENABLED=true
GLOBAL_BREAKING_NEWS_TITLE=🚨 글로벌 속보 TOP 3
GLOBAL_BREAKING_NEWS_COUNT=3
GLOBAL_BREAKING_NEWS_LOOKBACK_HOURS=24
GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES=true
GLOBAL_BREAKING_NEWS_QUERIES=
GLOBAL_BREAKING_SOCIAL_FEEDS=
```

영향력 있는 인물의 SNS 글을 추가하려면, 공개 RSS/Atom feed 또는 RSS 변환 URL을 아래처럼 넣을 수 있습니다.

```text
GLOBAL_BREAKING_SOCIAL_FEEDS=Elon Musk|https://example.com/elon/rss, Fed Chair|https://example.com/powell/rss
```

주의: X, Threads, Truth Social 같은 SNS는 공식 API/로그인/유료 권한이 필요한 경우가 많습니다. 이 자동화는 기본적으로 공개 RSS/Atom 또는 사용자가 제공한 feed URL을 읽는 방식입니다.

텔레그램 표시 예시:

```text
🚨 글로벌 속보 TOP 3
기준: 최근 24시간 이내 / 경제영향 필터 통과 기사 중 발행시각 최신순

1. 🛢️ [원자재·유가] CNBC 속보: 원자재·유가 이슈 — 물가·운송비·에너지·식품 원가 변동 가능성
출처: CNBC / 수집: 실제 뉴스 사이트 RSS / 발행: 06-28 09:15
경제영향: 물가·운송비·에너지·식품 원가 변동 가능성
원문제목: Oil prices rise after...
근거자료: 링크1
```

## 글로벌 경제 위험 알림 추가

`GLOBAL_MACRO_ALERT_ENABLED=true`이면 오늘의 핫이슈와 별도로 **시장 충격 가능성이 있는 글로벌 이슈**를 분리해서 보냅니다. 기본 추적 범위는 아래와 같습니다.

- 전쟁·확전·지정학 리스크
- 질병·감염병·팬데믹 위험
- 원·달러 환율 급등락, 달러인덱스, 외환시장
- 국제유가, 금, 구리, 곡물 등 원자재 급등락
- 미국 기준금리, 연준/FOMC, 국채금리 급등락
- 시장 루머·가십, 인수설·매각설·제재설
- 로이터/블룸버그 속보성 글로벌 시장 기사

기본 검색어를 그대로 쓰려면 `GLOBAL_MACRO_ALERT_TOPICS`를 비워두면 됩니다. 직접 조정하려면 아래처럼 입력하세요.

```text
GLOBAL_MACRO_ALERT_ENABLED=true
GLOBAL_MACRO_ALERT_TITLE=🌍 글로벌 경제 위험 알림
GLOBAL_MACRO_ALERT_TOPICS=로이터 속보 글로벌 경제 시장, 블룸버그 속보 글로벌 시장 경제, 원달러 환율 급등 급락, 국제유가 급등 급락, 미국 기준금리 연준 FOMC
GLOBAL_MACRO_ALERT_COUNT=7
GLOBAL_MACRO_ALERT_LOOKBACK_HOURS=24
```

텔레그램에서는 제목 앞에 `[전쟁·지정학]`, `[환율·달러]`, `[원자재·유가]`, `[금리·채권]`, `[시장루머·가십]` 같은 위험 태그가 붙습니다. 영문 Reuters/Bloomberg 제목은 오역을 피하기 위해 한국어 요약 제목과 원문 제목을 함께 표시합니다.

## 텔레그램 표시 예시

```text
🔥 오늘의 핫이슈 · 카드뉴스 · 작성글 후보
분야 필터: 경제·금융 우선
수집 기준: 최근 24시간 이내
정렬 기준: 종합 관심도 순 = Google Trends 조회수 + 네이버 뉴스량 + 네이버 DataLab 상대지수
근거자료 포함: 8/10개 항목
근거자료는 네이버 뉴스 우선, 부족하면 Google News로 보완합니다.

🚨 글로벌 속보 TOP 3
기준: 최근 24시간 이내 / 경제영향 필터 통과 기사 중 발행시각 최신순

1. 🏦 [금리·채권] Federal Reserve 속보: 금리·채권 이슈 — 대출금리·채권금리·주식 밸류에이션·부동산 심리 영향
출처: Federal Reserve / 수집: 공식 기관 피드 / 발행: 06-28 08:30
경제영향: 대출금리·채권금리·주식 밸류에이션·부동산 심리 영향
근거자료: 링크1

🌍 글로벌 경제 위험 알림
대상: 전쟁·질병·환율·원자재·금리·시장루머 및 로이터/블룸버그 속보성 기사

1. 💱 [환율·달러] 원·달러 환율 급등 관련 기사 제목
출처: 로이터 / 시각: 06-28 09:15
핵심영향: 수입물가·해외직구 원가·외국인 수급 영향
근거자료:
  1) 기사 제목 (언론사 · 06-28 09:15) / 링크1

🔥 오늘의 핫이슈 TOP 10

1. [경제·금융] 기준금리 전망
관심도: 148,000점 / Google 조회수: 10.0만+ / 근거강도: 강함
네이버 신호: 최근뉴스 6건 / DataLab 72.5
수집경로: google_trends_rss_24h
작성각도: 금리 변화 → 가계부담/저축전략 → 확인할 금융상품 포인트
근거자료:
  1) 기사 제목 (언론사 · 06-26 08:31) / 링크1
  2) 기사 제목 (언론사 · 06-26 08:12) / 링크2

📌 별도 추적 이슈

1. [기타] 국민연금 환율
관심도: 32,000점 / 근거강도: 보통
근거자료:
  1) 기사 제목 (언론사 · 06-26 11:20) / 링크1
```


## 자동 실행 일정

GitHub Actions는 UTC 기준으로 동작하므로, 한국시간 기준 아래 7회 실행되도록 설정했습니다.

| 한국시간(KST) | UTC cron 실행 시간 | 용도 예시 |
|---|---:|---|
| 오전 5:57 | 전일 20:57 UTC | 새벽 주요 이슈 확인 |
| 오전 9:15 | 00:15 UTC | 출근 후 오전 이슈 확인 |
| 오전 11:28 | 02:28 UTC | 오전장·오전 뉴스 반영 |
| 오후 2:07 | 05:07 UTC | 점심 이후 이슈 반영 |
| 오후 3:41 | 06:41 UTC | 장중/오후 이슈 반영 |
| 오후 8:02 | 11:02 UTC | 저녁 주요 이슈 정리 |
| 오후 10:03 | 13:03 UTC | 야간 마감 이슈 정리 |

워크플로우 설정값:

```yaml
schedule:
  - cron: "57 20 * * *"
  - cron: "15 0 * * *"
  - cron: "28 2 * * *"
  - cron: "7 5 * * *"
  - cron: "41 6 * * *"
  - cron: "2 11 * * *"
  - cron: "3 13 * * *"
```

## GitHub Actions 수동 실행 옵션

`Actions → daily-adsense-seo → Run workflow`에서 아래 값을 조정할 수 있습니다.

| 옵션 | 기본값 | 설명 |
|---|---:|---|
| `topics` | 비움 | 특정 주제만 보고 싶을 때 쉼표/줄바꿈으로 입력 |
| `special_issues` | 비움 | 오늘의 핫이슈와 별개로 고정 추적할 이슈 |
| `special_issue_title` | `📌 별도 추적 이슈` | 별도 이슈 섹션 제목 |
| `special_issue_count` | `5` | 별도 이슈 표시 개수 |
| `special_issue_category_filter` | `all` | 별도 이슈 카테고리 필터 |
| `global_macro_alert_enabled` | `true` | 글로벌 경제 위험 알림 사용 여부 |
| `global_macro_alert_title` | `🌍 글로벌 경제 위험 알림` | 글로벌 위험 알림 섹션 제목 |
| `global_macro_alert_topics` | 비움 | 비우면 기본 위험 키워드 묶음 사용. 직접 지정 가능 |
| `global_macro_alert_count` | `7` | 글로벌 위험 알림 표시 개수 |
| `global_macro_alert_lookback_hours` | `24` | 글로벌 위험 알림 최근 자료 기준 시간 |
| `global_breaking_news_enabled` | `true` | 글로벌 속보 TOP 3 사용 여부 |
| `global_breaking_news_title` | `🚨 글로벌 속보 TOP 3` | 글로벌 속보 섹션 제목 |
| `global_breaking_news_count` | `3` | 글로벌 속보 표시 개수 |
| `global_breaking_news_lookback_hours` | `24` | 글로벌 속보 최근 자료 기준 시간 |
| `global_breaking_news_use_direct_sites` | `true` | Google News RSS 부족 시 실제 뉴스/공식 RSS 보조 확인 |
| `global_breaking_news_queries` | 비움 | 비우면 기본 Reuters/Bloomberg/시장 속보 묶음 사용 |
| `global_breaking_social_feeds` | 비움 | 영향력 인물 SNS/RSS/Atom feed. `이름|URL` 형식 |
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
- `special_issue_items_YYYYMMDD.json`: 별도 추적 이슈와 근거 기사 데이터
- `global_macro_alert_items_YYYYMMDD.json`: 글로벌 경제 위험 알림과 근거 기사 데이터
- `idea_items_YYYYMMDD.csv`: 순위, 관심도, 네이버 신호, 추천 용도, 근거 기사 링크 요약

## 텔레그램에서 주제 입력 → 맞춤 리포트 재전송

`telegram-topic-listener.yml` 워크플로우가 추가되었습니다. 텔레그램에 특정 주제를 보내면 다음 실행 시점에 아래 내용을 별도 리포트로 다시 보냅니다.

- 관련 핫이슈 TOP 5
- 관련 키워드
- 카드뉴스 후보
- 카드뉴스 스크립트
- 작성글 후보
- 근거 기사 링크
- 주제와 연관된 글로벌 속보 보강

### 사용 예시

텔레그램 채널/방에 아래처럼 입력하세요.

```text
/topic 원달러 환율
```

또는 한국어로 입력해도 됩니다.

```text
주제: 엔비디아 실적
토픽 트럼프 관세
핫이슈 국제유가 급등
```

기본값에서는 `/topic`, `주제:`, `토픽`, `핫이슈` 같은 명령형 메시지만 처리합니다. 일반 문장도 전부 주제로 처리하고 싶으면 GitHub Variables에 아래 값을 추가하세요.

```text
TELEGRAM_TOPIC_ACCEPT_PLAIN=true
```

처음 운영할 때는 오작동 방지를 위해 `false`를 권장합니다.

### GitHub Variables 권장값

`Settings → Secrets and variables → Actions → Variables`에 필요하면 아래 값을 추가하세요.

```text
TELEGRAM_TOPIC_ACCEPT_PLAIN=false
TELEGRAM_TOPIC_LOOKBACK_HOURS=48
TELEGRAM_TOPIC_NEWS_LINKS=8
TELEGRAM_TOPIC_INCLUDE_GLOBAL_BREAKING=true
TELEGRAM_TOPIC_GLOBAL_BREAKING_COUNT=3
TELEGRAM_TOPIC_MAX_UPDATES=20
```

특정 채팅방/채널에서 온 메시지만 처리하려면 아래 값을 추가합니다. 비워두면 `TELEGRAM_CHAT_ID`를 기준으로 제한합니다.

```text
TELEGRAM_TOPIC_ALLOWED_CHAT_IDS=-1001234567890
```

### 실행 방식

GitHub Actions는 텔레그램 메시지를 실시간으로 항상 듣고 있는 서버가 아니기 때문에, 이 패키지는 `telegram-topic-listener.yml`을 약 10분 간격으로 실행해 새 메시지를 확인합니다. 더 빠른 실시간 반응이 필요하면 같은 `telegram_topic_listener.py` 로직을 Railway/Vercel/Cloudflare Workers 같은 webhook 서버로 옮기는 방식이 좋습니다.


## 텔레그램 주제 입력 실시간 응답: Vercel Webhook 방식

이 패키지는 텔레그램에 주제를 입력하면 즉시 Vercel 함수가 받아서 관련 리포트를 다시 보내는 webhook 방식을 지원합니다.

```text
Telegram → Vercel /api/telegram_webhook → 주제 분석 리포트 → Telegram 재전송
```

기존 10분 폴링용 `telegram-topic-listener.yml` 워크플로우는 webhook과 충돌할 수 있어 제거했습니다. 자세한 설정 순서는 `README_VERCEL_WEBHOOK.md`를 확인하세요.

### 사용 예시

```text
/topic 원달러 환율
/topic 국제유가 급등
주제: 엔비디아 실적
핫이슈 트럼프 관세
```

### Vercel 필수 환경변수

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
GEMINI_API_KEY
TELEGRAM_WEBHOOK_SECRET
```

### Webhook 등록

GitHub Actions에서 아래 워크플로우를 수동 실행합니다.

```text
Actions → telegram-webhook-control → Run workflow → action=set
```

`TELEGRAM_WEBHOOK_URL`에는 Vercel 주소를 넣습니다.

```text
https://YOUR_PROJECT.vercel.app
```

등록 후 실제 Telegram webhook endpoint는 아래가 됩니다.

```text
https://YOUR_PROJECT.vercel.app/api/telegram_webhook
```
