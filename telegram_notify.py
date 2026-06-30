# Telegram News Vercel Webhook

텔레그램 봇으로 키워드 질문을 보내면 Vercel 웹훅이 즉시 받아서 최신 뉴스 후보를 수집하고, OpenAI로 딥브리핑 또는 카드뉴스를 만들어 답장하는 프로젝트입니다.

## 가능한 기능

- 텔레그램 질문 즉시 수신
- 키워드 기준 최신 뉴스 후보 수집
- 키워드 딥브리핑 답장
- `실시간 검색어`, `지금 뜨는 이슈` 요청 시 뉴스 기반 급상승 이슈 TOP 10 답장
- `카드뉴스 만들어줘` 요청 시 카드뉴스 이미지 생성 후 전송
- `카드뉴스 스크립트` 요청 시 제작 스크립트만 텍스트로 전송
- 카드뉴스 이미지 생성 실패 시 제작 스크립트를 fallback으로 전송
- `모닝브리핑` 요청 시 당일 브리핑 전송
- Vercel Cron으로 매일 한국시간 오전 7시 30분 자동 모닝브리핑

## 파일 구조

```text
.
├─ api/
│  ├─ telegram-webhook.js
│  ├─ morning-briefing.js
│  ├─ setup-webhook.js
│  ├─ test-message.js
│  ├─ debug-webhook.js
│  ├─ test-openai.js
│  └─ test-news.js
├─ lib/
│  ├─ config.js
│  ├─ handlers.js
│  ├─ intent.js
│  ├─ news.js
│  ├─ openai.js
│  ├─ prompts.js
│  ├─ storage.js
│  └─ telegram.js
├─ package.json
├─ vercel.json
├─ .env.example
└─ README.md
```

## Vercel 환경변수

Vercel 프로젝트의 `Settings` → `Environment Variables`에 아래 값을 등록하세요.

```text
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
SETUP_SECRET
CRON_SECRET
OPENAI_TEXT_MODEL
OPENAI_IMAGE_MODEL
NEWS_LOOKBACK_HOURS
PUBLIC_BASE_URL
CARD_SCRIPT_TTL_SECONDS
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
```

필수 값은 아래 6개입니다.

```text
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
SETUP_SECRET
CRON_SECRET
```

권장 기본값:

```text
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-4.1-mini
NEWS_LOOKBACK_HOURS=48
PUBLIC_BASE_URL=https://your-vercel-domain.vercel.app
CARD_SCRIPT_TTL_SECONDS=604800
```

`TELEGRAM_WEBHOOK_SECRET`, `SETUP_SECRET`, `CRON_SECRET`는 서로 다른 긴 랜덤 문자열로 넣는 것을 권장합니다.

중요: `TELEGRAM_WEBHOOK_SECRET`은 텔레그램 웹훅 검증 토큰으로 전달되므로 영문, 숫자, 밑줄(`_`), 하이픈(`-`)만 사용하세요. 느낌표(`!`) 같은 특수문자는 쓰지 않는 편이 안전합니다.

`UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`은 선택 사항입니다. 이 값을 넣으면 최근 생성한 카드뉴스 제작 스크립트를 저장했다가 `카드뉴스 스크립트` 요청 시 다시 보여줄 수 있습니다. 넣지 않아도 카드뉴스 생성과 키워드별 스크립트 생성은 정상 동작하지만, 서버리스 인스턴스가 바뀌면 "최근 생성본" 재조회는 안정적으로 보장되지 않습니다.

## 배포 순서

1. 이 폴더 내용을 GitHub 저장소에 올립니다.
2. Vercel에서 해당 GitHub 저장소를 Import합니다.
3. 위 환경변수를 Vercel에 등록합니다.
4. 배포가 끝난 뒤 아래 주소를 브라우저에서 엽니다.

```text
https://your-vercel-domain.vercel.app/api/setup-webhook?secret=SETUP_SECRET
```

정상이라면 JSON 응답에 `ok: true`가 표시됩니다.

## 텔레그램에서 사용하기

일반 키워드 딥브리핑:

```text
반도체
원달러 환율 전망
미국 고용지표가 코스피에 미치는 영향
```

카드뉴스 제작:

```text
반도체 카드뉴스 만들어줘
원달러 환율 전망 카드뉴스
미국 고용지표 카드뉴스 제작
```

카드뉴스 제작 스크립트만 받기:

```text
반도체 카드뉴스 스크립트
원달러 환율 전망 카드뉴스 기획안
카드뉴스 스크립트
```

`카드뉴스 스크립트`처럼 키워드 없이 요청하면 최근 생성한 카드뉴스의 제작 스크립트를 다시 보내려고 시도합니다. 이 기능을 안정적으로 쓰려면 `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`을 설정하세요.

뉴스 기반 급상승 이슈 보기:

```text
실시간 검색어
지금 뜨는 이슈
핫이슈 순위
```

이 기능은 포털 공식 실시간 검색어 원본이 아니라, 최근 뉴스 발행 빈도와 반복 등장, 영향도를 기준으로 만든 뉴스 기반 랭킹입니다.

모닝브리핑 다시 받기:

```text
모닝브리핑
```

도움말:

```text
/help
```

내 chat_id 확인:

```text
/chatid
```

`/api/test-message`에서 `Bad Request: chat not found`가 나오면 Vercel의 `TELEGRAM_CHAT_ID`가 실제 채팅방 ID와 다른 상태입니다. 텔레그램 봇에게 `/chatid`를 보내고, 돌아온 숫자를 `TELEGRAM_CHAT_ID`에 넣은 뒤 Vercel에서 다시 Redeploy하세요.

## 자동 모닝브리핑 시간

`vercel.json`에 매일 `22:30 UTC`로 설정되어 있습니다. 한국시간으로는 다음 날 오전 7시 30분입니다.

```json
{
  "crons": [
    {
      "path": "/api/morning-briefing",
      "schedule": "30 22 * * *"
    }
  ]
}
```

## 수동 모닝브리핑 호출

브라우저나 HTTP 클라이언트에서 아래 주소를 호출하면 됩니다.

```text
https://your-vercel-domain.vercel.app/api/morning-briefing?secret=CRON_SECRET
```

## 문제 확인용 테스트 주소

배포와 웹훅 연결은 성공했는데 텔레그램에서 답장이 오지 않으면 아래 순서로 확인하세요.

1. 먼저 Vercel 서버가 텔레그램으로 메시지를 보낼 수 있는지 확인합니다.

```text
https://your-vercel-domain.vercel.app/api/test-message?secret=SETUP_SECRET
```

이 주소를 열었을 때 텔레그램으로 테스트 메시지가 오면 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`는 정상입니다.

만약 아래 오류가 나오면 `TELEGRAM_CHAT_ID`가 틀린 것입니다.

```text
Bad Request: chat not found
```

텔레그램 봇에게 `/chatid`를 보내고, 봇이 알려준 값을 Vercel의 `TELEGRAM_CHAT_ID`에 다시 넣으세요.

2. 웹훅이 제대로 연결되어 있는지 확인합니다.

```text
https://your-vercel-domain.vercel.app/api/debug-webhook?secret=SETUP_SECRET
```

응답의 `telegram.result.url`이 아래 주소와 비슷해야 합니다.

```text
https://your-vercel-domain.vercel.app/api/telegram-webhook
```

3. 텍스트 답장이 계속 실패하면 `OPENAI_TEXT_MODEL`을 아래 값으로 설정한 뒤 Redeploy하세요.

```text
OPENAI_TEXT_MODEL=gpt-4.1-mini
```

4. OpenAI 연결만 따로 확인합니다.

```text
https://your-vercel-domain.vercel.app/api/test-openai?secret=SETUP_SECRET
```

5. 뉴스 수집만 따로 확인합니다.

```text
https://your-vercel-domain.vercel.app/api/test-news?secret=SETUP_SECRET
```

`/api/test-message`는 성공하는데 일반 키워드 답변이 실패하면, 대부분 `/api/test-openai` 또는 `/api/test-news` 쪽에서 원인이 드러납니다.

## 기존 getUpdates 방식에서 전환할 때

기존 GitHub Actions 폴링 방식이나 다른 봇 서버에서 `getUpdates`를 쓰고 있었다면, 웹훅 등록 후에는 중복 처리를 피하기 위해 기존 폴링 워크플로를 꺼두는 편이 좋습니다.

이미 다른 웹훅이 걸려 있으면 아래 주소로 해제할 수 있습니다.

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook
```

그 다음 다시 `setup-webhook` 주소를 열면 됩니다.

## 참고 사항

- 뉴스 수집은 Google News RSS 기반입니다. 기사 발행 시각을 기준으로 최근 자료를 우선 사용합니다.
- `실시간 검색어` 기능은 포털 공식 검색어 순위가 아니라 뉴스 기반 급상승 이슈 랭킹입니다.
- 카드뉴스 이미지는 OpenAI 이미지 생성 기능을 사용합니다.
- 이미지 안의 한글 텍스트 품질은 생성 모델 상태에 따라 달라질 수 있습니다. 그래서 텔레그램 사진 캡션에도 핵심 설명과 출처를 같이 넣습니다.
- 카드뉴스 이미지 생성에 실패하면 제작 스크립트를 대신 보내도록 처리했습니다.
- 투자 판단을 대신하는 용도가 아니라, 이슈 파악과 자료 정리용으로 사용하는 것을 권장합니다.
