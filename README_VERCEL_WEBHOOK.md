# Telegram 실시간 주제 분석: Vercel Webhook 방식

이 버전은 GitHub Actions가 10분마다 텔레그램을 확인하는 방식이 아니라, 텔레그램 메시지가 들어오는 즉시 Vercel 서버리스 함수가 받아 처리하는 방식입니다.

```text
Telegram message
→ Vercel /api/telegram_webhook
→ 관련 뉴스·글로벌 속보 수집
→ 핫이슈 / 키워드 / 카드뉴스 후보 / 카드뉴스 스크립트 / 작성글 후보 생성
→ Telegram 재전송
```

## 1. GitHub에 업로드할 파일

아래 파일이 추가되었습니다.

```text
api/telegram_webhook.py
scripts/telegram_webhook_control.py
vercel.json
.github/workflows/telegram-webhook-control.yml
README_VERCEL_WEBHOOK.md
```

그리고 기존 10분 폴링용 파일은 webhook과 충돌할 수 있어 제거했습니다.

```text
.github/workflows/telegram-topic-listener.yml
```

Telegram은 webhook이 활성화되어 있으면 `getUpdates` 방식과 함께 쓰기 어렵습니다. 따라서 Vercel webhook을 쓰는 동안에는 10분 폴링 워크플로우를 사용하지 않는 것이 안전합니다.

## 2. Vercel 환경변수 설정

Vercel 프로젝트의 `Settings → Environment Variables`에 아래 값을 넣습니다.

### 필수

```text
TELEGRAM_BOT_TOKEN=텔레그램 봇 토큰
TELEGRAM_CHAT_ID=텔레그램 채널 또는 채팅 ID
GEMINI_API_KEY=Gemini API 키
TELEGRAM_WEBHOOK_SECRET=아무도 모르는 긴 임의 문자열
```

### 권장

```text
GEMINI_MODEL=gemini-2.5-flash
NEWS_PROVIDER=naver_first
GOOGLE_TRENDS_GEO=KR
TELEGRAM_TOPIC_ACCEPT_PLAIN=false
TELEGRAM_TOPIC_LOOKBACK_HOURS=48
TELEGRAM_TOPIC_NEWS_LINKS=8
TELEGRAM_TOPIC_INCLUDE_GLOBAL_BREAKING=true
TELEGRAM_TOPIC_GLOBAL_BREAKING_COUNT=3
GLOBAL_BREAKING_NEWS_USE_DIRECT_SITES=true
GLOBAL_BREAKING_SOCIAL_FEEDS=Fed Press|https://www.federalreserve.gov/feeds/press_all.xml, Fed Speeches|https://www.federalreserve.gov/feeds/speeches.xml, ECB Press|https://www.ecb.europa.eu/rss/press.html, WHO Disease Outbreak|https://www.who.int/rss-feeds/news-english.xml
```

네이버 뉴스 API를 같이 쓰려면 아래도 넣습니다.

```text
NAVER_CLIENT_ID=네이버 client id
NAVER_CLIENT_SECRET=네이버 client secret
```

## 3. GitHub Secrets / Variables 설정

GitHub Actions에서 Telegram webhook을 등록하려면 GitHub에도 아래 값을 넣습니다.

### GitHub Secrets

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
```

`TELEGRAM_WEBHOOK_SECRET`은 Vercel에 넣은 값과 반드시 같아야 합니다.

### GitHub Variables

```text
TELEGRAM_WEBHOOK_URL=https://YOUR_PROJECT.vercel.app
```

전체 endpoint를 넣어도 됩니다.

```text
TELEGRAM_WEBHOOK_URL=https://YOUR_PROJECT.vercel.app/api/telegram_webhook
```

## 4. Vercel 배포

GitHub 저장소를 Vercel에 연결해 배포합니다. 배포 후 아래 주소가 열리면 정상입니다.

```text
https://YOUR_PROJECT.vercel.app/api/telegram_webhook
```

정상이라면 JSON이 보입니다.

```json
{"ok": true, "service": "gooddaynews-telegram-webhook"}
```

## 5. Telegram webhook 등록

GitHub에서 아래 워크플로우를 수동 실행합니다.

```text
Actions → telegram-webhook-control → Run workflow
```

입력값:

```text
action: set
webhook_url: 비워도 됨. 단, vars.TELEGRAM_WEBHOOK_URL이 있어야 함
drop_pending_updates: true
```

확인하려면 다시 수동 실행합니다.

```text
action: info
```

끄려면 아래처럼 실행합니다.

```text
action: delete
```

## 6. 텔레그램 사용법

기본값에서는 명령어 형태만 인식합니다.

```text
/topic 원달러 환율
/topic 국제유가 급등
주제: 엔비디아 실적
핫이슈 트럼프 관세
```

그냥 단어만 보내도 인식하게 하려면 Vercel 환경변수와 GitHub Variables에 아래 값을 넣습니다.

```text
TELEGRAM_TOPIC_ACCEPT_PLAIN=true
```

다만 일반 대화까지 전부 주제로 인식할 수 있으므로 처음에는 `false`를 권장합니다.

## 7. 주의사항

- Vercel Hobby 플랜에서는 함수 실행 시간이 기본 10초이고, `vercel.json`에서 60초까지 늘리도록 설정했습니다.
- 리포트 생성이 60초를 넘으면 Telegram이 같은 요청을 재시도할 수 있어 중복 응답이 생길 수 있습니다.
- 그래서 처음 운영은 아래처럼 가볍게 시작하는 것을 권장합니다.

```text
TELEGRAM_TOPIC_NEWS_LINKS=5
TELEGRAM_TOPIC_GLOBAL_BREAKING_COUNT=2
TELEGRAM_TOPIC_LOOKBACK_HOURS=24
```
