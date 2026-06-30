# Gooddaynews 보정 내역

이 패치는 사용자가 요청한 아래 운영 기준을 반영합니다.

## 반영 항목

1. 기본 지역/언어/시간 기준을 한국으로 고정
   - `DEFAULT_REGION=KR`
   - `DEFAULT_LOCALE=ko-KR`
   - `DEFAULT_TIMEZONE=Asia/Seoul`

2. 근거 기사는 최근 48시간 이내만 사용
   - `SUPPORTING_NEWS_MAX_AGE_HOURS=48`
   - `EXCLUDE_UNKNOWN_PUBLISHED_AT=true`
   - 발행시각이 없거나 48시간을 넘은 기사는 근거자료에서 제외

3. `/topic 오늘 날씨` 지원
   - 기본 지역은 서울
   - Open-Meteo 기반, 별도 API 키 불필요
   - `WEATHER_DEFAULT_CITY`, `WEATHER_DEFAULT_LAT`, `WEATHER_DEFAULT_LON`으로 지역 변경 가능

4. 한국어 인물명 동명이인 경고
   - 2~4글자 한국어 인물명으로 보이는 주제는 직함/소속/분야 맥락을 확인
   - 맥락이 섞이거나 부족하면 `인물 키워드 검증` 경고 출력

5. Telegram 기사 URL 표시 개선
   - 본문에는 `링크1`, `링크2`로 표시
   - Vercel webhook 응답은 `inline_keyboard` 버튼으로 기사 링크 제공

6. daily-adsense-seo 예약 실행 복구
   - 05:57 / 09:15 / 11:28 / 14:07 / 15:41 / 20:02 / 22:03 KST

## Vercel 설정

Vercel Project → Settings → General → Root Directory:

```text
vercel-webhook
```

Vercel Environment Variables에 아래 값을 추가/확인하세요.

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

기존 필수값도 유지해야 합니다.

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
GEMINI_API_KEY
```

환경변수 변경 후에는 반드시 Vercel에서 Redeploy 하세요.

## 테스트

```text
/ping
/topic 오늘 날씨
/topic 원달러 환율
/topic 안정환
```

브라우저 상태 확인:

```text
https://gooddaynews-ten.vercel.app/api/telegram_webhook
```

정상 버전:

```text
topic-report-flask-kr48-weather-personguard-2026-06-30-01
```
