export function env(name, fallback = undefined) {
  const value = process.env[name] || fallback;

  if (value === undefined || value === "") {
    throw new Error(`Missing required environment variable: ${name}`);
  }

  return value;
}

export function optionalEnv(name, fallback = "") {
  return process.env[name] || fallback;
}

export function textModel() {
  return optionalEnv("OPENAI_TEXT_MODEL", "gpt-4.1-mini");
}

export function imageModel() {
  return optionalEnv("OPENAI_IMAGE_MODEL", "gpt-4.1-mini");
}

export function newsLookbackHours() {
  const rawValue = optionalEnv("NEWS_LOOKBACK_HOURS", "48");
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 48;
}

export function cardScriptTtlSeconds() {
  const rawValue = optionalEnv("CARD_SCRIPT_TTL_SECONDS", "604800");
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 604800;
}

export function kstDateLabel() {
  const formatter = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long",
    day: "numeric",
    weekday: "short"
  });

  return formatter.format(new Date()).replace(/\s+/g, " ");
}

export function baseUrlFromRequest(request) {
  const configured = optionalEnv("PUBLIC_BASE_URL");
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const url = new URL(request.url);
  return `${url.protocol}//${url.host}`;
}
