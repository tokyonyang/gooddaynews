import { kstDateLabel } from "./config.js";

export function buildMorningBriefingPrompt(sourceText) {
  const dateLabel = kstDateLabel();

  return `
오늘 날짜: ${dateLabel}

아래 뉴스 후보를 바탕으로 한국어 모닝 브리핑을 작성해줘.

작성 원칙:
- 제공된 뉴스 후보에 있는 내용만 근거로 사용한다.
- 확인되지 않은 수치, 환율, 주가, 날짜, 정책 발표는 절대 지어내지 않는다.
- 같은 이슈가 여러 기사에 반복되면 하나로 묶는다.
- 뉴스 후보 전체에서 오늘 많이 언급되거나 시장 영향이 큰 핫이슈 키워드 5개를 먼저 뽑는다.
- 핫이슈 키워드는 해시태그 형태로 쓰고, 각 키워드마다 한 줄 이유를 붙인다.
- 투자 조언처럼 단정하지 말고, "체크할 변수" 중심으로 쓴다.
- 텔레그램으로 보낼 것이므로 전체를 3,800자 안팎으로 압축한다.
- 출처 링크는 마지막에 3~5개만 짧게 모아준다.

반드시 아래 형식을 지켜줘:

🌅 ${dateLabel} 모닝 브리핑

좋은 아침입니다! 오늘 꼭 알아두면 좋을 주요 이슈를 5분 안에 정리해 드립니다.

🔥 오늘의 핫이슈 키워드
#키워드1 - 선정 이유
#키워드2 - 선정 이유
#키워드3 - 선정 이유
#키워드4 - 선정 이유
#키워드5 - 선정 이유

🇰🇷 국내 주요 뉴스
① ...
② ...
③ ...

📈 경제 & 증시
...

🌎 국제 뉴스
...

💹 투자 포인트
✅ ...
✅ ...
✅ ...

🌤️ 오늘 한 줄 요약
"..."

🔗 참고한 주요 기사
- 기사 제목: 링크

뉴스 후보:
${sourceText}
`.trim();
}

export function buildKeywordBriefingPrompt(keyword, sourceText) {
  return `
오늘 날짜: ${kstDateLabel()}
사용자 질문 또는 키워드: ${keyword}

아래 뉴스 후보를 바탕으로 텔레그램 답장을 작성해줘.

작성 원칙:
- 제공된 뉴스 후보에 있는 내용만 근거로 사용한다.
- 확인되지 않은 수치, 주가, 환율, 일정, 정책 발표는 지어내지 않는다.
- 사용자가 묻는 키워드와 직접 관련 있는 내용만 우선한다.
- 단순 요약이 아니라 "왜 중요한지", "무엇을 더 봐야 하는지"까지 정리한다.
- 투자 권유나 매수/매도 판단처럼 쓰지 않는다.
- 텔레그램 답장이므로 3,500자 안팎으로 압축한다.
- 마지막에 참고 기사 링크 3~5개를 붙인다.

반드시 아래 형식을 지켜줘:

🔎 키워드 딥브리핑: ${keyword}

한 줄 결론:
...

핵심 내용
① ...
② ...
③ ...

왜 중요한가
...

체크 포인트
✅ ...
✅ ...
✅ ...

관련 리스크
- ...
- ...

참고 기사
- 기사 제목: 링크

뉴스 후보:
${sourceText}
`.trim();
}

export function buildTrendRankingPrompt(sourceText) {
  return `
오늘 날짜: ${kstDateLabel()}

아래 뉴스 후보를 바탕으로 "뉴스 기반 급상승 이슈 TOP 10"을 작성해줘.

중요:
- 이것은 포털 공식 실시간 검색어 순위가 아니다.
- 최근 뉴스 발행 빈도, 여러 섹션 반복 등장, 사회/경제 영향도, 시장 관심도를 근거로 순위를 추정한다.
- 제공된 뉴스 후보에 있는 내용만 사용한다.
- 확인되지 않은 수치, 순위 출처, 검색량은 지어내지 않는다.
- 텔레그램으로 보낼 것이므로 3,500자 안팎으로 압축한다.

반드시 아래 형식을 지켜줘:

🔥 지금 뜨는 이슈 TOP 10
기준: 최근 뉴스 빈도, 반복 등장, 영향도 기준의 뉴스 기반 랭킹입니다.

1. #키워드
- 왜 뜨나: ...
- 체크 포인트: ...

2. #키워드
- 왜 뜨나: ...
- 체크 포인트: ...

...

한 줄 흐름:
"..."

참고 기사
- 기사 제목: 링크

뉴스 후보:
${sourceText}
`.trim();
}

export function buildCardScriptPrompt(keyword, sourceText) {
  return `
오늘 날짜: ${kstDateLabel()}
카드뉴스 주제: ${keyword}

아래 뉴스 후보를 바탕으로 카드뉴스 1장짜리 기획안을 JSON으로 작성해줘.

작성 원칙:
- 제공된 뉴스 후보에 있는 내용만 근거로 사용한다.
- 숫자, 일정, 기관명, 시장 반응은 기사에 있을 때만 쓴다.
- 제목은 짧고 강하게 쓴다.
- 본문 문장은 모바일 카드뉴스에 들어갈 수 있게 짧게 쓴다.
- 투자 권유처럼 쓰지 않는다.
- JSON 외의 설명은 절대 쓰지 않는다.

반드시 이 JSON 구조만 반환해:
{
  "title": "카드뉴스 제목",
  "subtitle": "한 줄 부제",
  "bullets": [
    "핵심 문장 1",
    "핵심 문장 2",
    "핵심 문장 3"
  ],
  "footer": "체크할 변수 한 줄",
  "caption": "텔레그램 사진 캡션용 짧은 설명",
  "sources": [
    "기사 제목: 링크"
  ]
}

뉴스 후보:
${sourceText}
`.trim();
}

export function formatCardScriptMessage(keyword, cardScript, options = {}) {
  const sources = (cardScript.sources || []).slice(0, 5);
  const bullets = (cardScript.bullets || []).slice(0, 5);
  const storedLabel = options.fromStorage ? "저장된 제작 스크립트" : "제작 스크립트";

  return [
    `🧾 카드뉴스 ${storedLabel}: ${keyword}`,
    "",
    `제목: ${cardScript.title || "-"}`,
    `부제: ${cardScript.subtitle || "-"}`,
    "",
    "본문 문안:",
    ...bullets.map((bullet, index) => `${index + 1}. ${bullet}`),
    "",
    `하단 문구: ${cardScript.footer || "-"}`,
    `사진 캡션: ${cardScript.caption || "-"}`,
    "",
    "참고 기사:",
    ...(sources.length ? sources.map((source) => `- ${source}`) : ["- 없음"])
  ].join("\n");
}

export function buildCardImagePrompt(cardScript) {
  const bullets = (cardScript.bullets || []).slice(0, 3).join(" / ");

  return `
Create a premium Korean news card image for Telegram.

Canvas:
- Portrait social card, clean newsroom style, suitable for mobile.
- High contrast, modern editorial design.
- Use Korean typography.
- Keep text large and readable.
- Do not use logos, stock tickers, copyrighted brand marks, or fake newspaper mastheads.

Text to include exactly in Korean:
Title: ${cardScript.title}
Subtitle: ${cardScript.subtitle}
Bullets: ${bullets}
Footer: ${cardScript.footer}

Visual direction:
- Sophisticated financial-news visual style.
- Use simple charts, abstract market lines, calendar or globe motifs if relevant.
- Avoid clutter.
`.trim();
}
