# Gooddaynews Telegram Webhook

Vercel Root Directory: `vercel-webhook`

Endpoint: `/api/telegram_webhook`

Test commands:

- `/ping`
- `/topic 원달러 환율`
- `주제: 엔비디아 실적`


## 2026-06-30 보정 사항

- 기본 지역/언어/시간 기준: 한국 / ko-KR / Asia/Seoul
- `/topic` 근거 기사: 최근 48시간 이내 기사만 사용
- 발행시각 미확인 기사는 기본 제외
- `/topic 오늘 날씨` 요청 시 서울 기준 오늘 날씨 표시
- 2~4글자 한국어 인물명은 동명이인 가능성 경고
- 기사 URL은 본문에 길게 노출하지 않고 Telegram 링크 버튼으로 제공

필수 Vercel Variables:

```text
DEFAULT_REGION=KR
DEFAULT_LOCALE=ko-KR
DEFAULT_TIMEZONE=Asia/Seoul
SUPPORTING_NEWS_MAX_AGE_HOURS=48
EXCLUDE_UNKNOWN_PUBLISHED_AT=true
WEATHER_ENABLED=true
WEATHER_DEFAULT_CITY=서울
WEATHER_DEFAULT_LAT=37.5665
WEATHER_DEFAULT_LON=126.9780
PERSON_KEYWORD_GUARD=true
PERSON_KEYWORD_MIN_CONTEXT_MATCH=2
TELEGRAM_URL_BUTTONS=true
TELEGRAM_LINK_BUTTON_LIMIT=8
```
