const CARD_NEWS_PATTERNS = [
  /카드\s*뉴스/i,
  /카드뉴스/i,
  /카드\s*만들/i,
  /이미지\s*만들/i,
  /인포그래픽/i
];

const CARD_SCRIPT_PATTERNS = [
  /카드\s*뉴스.*스크립트/i,
  /카드뉴스.*스크립트/i,
  /스크립트.*카드\s*뉴스/i,
  /스크립트.*카드뉴스/i,
  /카드\s*뉴스.*기획안/i,
  /카드뉴스.*기획안/i,
  /카드\s*뉴스.*원고/i,
  /카드뉴스.*원고/i,
  /제작\s*스크립트/i,
  /제작안/i,
  /문안/i
];

const TREND_RANKING_PATTERNS = [
  /실시간\s*검색어/i,
  /실검/i,
  /급상승\s*검색어/i,
  /급상승\s*이슈/i,
  /지금\s*뜨는\s*이슈/i,
  /오늘\s*뜨는\s*이슈/i,
  /핫이슈\s*순위/i,
  /이슈\s*랭킹/i,
  /트렌드\s*순위/i
];

export function isHelpCommand(text) {
  return /^\/(start|help)(\s|$)/i.test(text.trim());
}

export function isChatIdCommand(text) {
  return /^\/chatid(\s|$)/i.test(text.trim());
}

export function isMorningBriefingRequest(text) {
  const clean = text.replace(/\s+/g, "");
  return /모닝브리핑|아침브리핑|오늘브리핑/.test(clean);
}

export function isTrendRankingRequest(text) {
  return TREND_RANKING_PATTERNS.some((pattern) => pattern.test(text));
}

export function isCardScriptRequest(text) {
  return CARD_SCRIPT_PATTERNS.some((pattern) => pattern.test(text));
}

export function isCardNewsRequest(text) {
  return CARD_NEWS_PATTERNS.some((pattern) => pattern.test(text));
}

export function extractCardKeyword(text) {
  return text
    .replace(/카드\s*뉴스/gi, " ")
    .replace(/카드뉴스/gi, " ")
    .replace(/카드\s*만들.*$/gi, " ")
    .replace(/이미지\s*만들.*$/gi, " ")
    .replace(/인포그래픽/gi, " ")
    .replace(/제작|생성|만들어줘|만들어|부탁|기준으로|관련|대한|으로/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function extractCardScriptKeyword(text) {
  return extractCardKeyword(
    text
      .replace(/스크립트/gi, " ")
      .replace(/기획안/gi, " ")
      .replace(/원고/gi, " ")
      .replace(/문안/gi, " ")
      .replace(/제작안/gi, " ")
  );
}

export function normalizeQuestion(text) {
  return text.replace(/\s+/g, " ").trim();
}

export const HELP_MESSAGE = `
궁금한 키워드나 질문을 그대로 보내주세요.

예)
반도체
원달러 환율 전망
미국 고용지표가 코스피에 미치는 영향

카드뉴스가 필요하면 이렇게 보내면 됩니다.
반도체 카드뉴스 만들어줘
원달러 환율 전망 카드뉴스

카드뉴스 스크립트만 필요하면 이렇게 보내면 됩니다.
반도체 카드뉴스 스크립트
카드뉴스 스크립트

지금 뜨는 이슈가 궁금하면 이렇게 보내면 됩니다.
실시간 검색어
지금 뜨는 이슈

내 텔레그램 chat_id를 확인하려면 이렇게 보내세요.
/chatid

오늘 모닝 브리핑을 다시 받고 싶으면 "모닝브리핑"이라고 보내주세요.
`.trim();
