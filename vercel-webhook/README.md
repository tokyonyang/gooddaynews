# Gooddaynews Vercel Telegram Webhook - Clean Build

이 폴더는 Vercel 전용 최소 웹훅 앱입니다. 기존 GitHub Actions 자동 리포트 코드와 분리되어 있습니다.

## Vercel 설정

Vercel Project → Settings → General → Root Directory:

```text
vercel-webhook
```

## 환경변수

Vercel Project → Settings → Environment Variables:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_WEBHOOK_SECRET=긴_랜덤_문자열
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
TELEGRAM_TOPIC_ACCEPT_PLAIN=false
TELEGRAM_TOPIC_NEWS_LINKS=8
```

## 배포 후 확인

```text
https://YOUR_PROJECT.vercel.app/api/telegram_webhook
```

정상 응답:

```json
{"ok": true, "service": "gooddaynews-telegram-webhook", "route": "/api/telegram_webhook"}
```

## Telegram webhook 등록

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://YOUR_PROJECT.vercel.app/api/telegram_webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>&drop_pending_updates=true
```

## 테스트 메시지

```text
/topic 원달러 환율
주제: 엔비디아 실적
핫이슈 국제유가 급등
```
