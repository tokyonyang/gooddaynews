export function safeErrorMessage(error) {
  const message = error instanceof Error ? error.message : String(error);

  return message
    .replace(/sk-[A-Za-z0-9_-]+/g, "sk-<hidden>")
    .replace(/bot\d+:[A-Za-z0-9_-]+/g, "bot<hidden-token>")
    .slice(0, 1000);
}

export function userFacingErrorMessage(error) {
  const message = safeErrorMessage(error);

  if (/OpenAI API error 401/.test(message)) {
    return "OpenAI API Key 인증에 실패했습니다. Vercel의 OPENAI_API_KEY 값을 확인해주세요.";
  }

  if (/OpenAI API error 403/.test(message)) {
    return "OpenAI API 접근 권한 문제가 있습니다. 모델 권한 또는 프로젝트 권한을 확인해주세요.";
  }

  if (/OpenAI API error 429/.test(message)) {
    return "OpenAI 사용량 한도 또는 rate limit에 걸렸습니다. 잠시 뒤 다시 시도해주세요.";
  }

  if (/model|does not exist|not found|unsupported/i.test(message)) {
    return "OpenAI 모델 설정 문제가 의심됩니다. Vercel의 OPENAI_TEXT_MODEL을 gpt-4.1-mini로 설정해보세요.";
  }

  if (/Google News RSS|fetch failed|ENOTFOUND|ECONNRESET|ETIMEDOUT/i.test(message)) {
    return "뉴스 수집 중 네트워크 오류가 발생했습니다. 잠시 뒤 다시 시도해주세요.";
  }

  return `내부 오류가 발생했습니다. 원인: ${message}`;
}
