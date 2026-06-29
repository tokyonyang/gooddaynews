import { cardScriptTtlSeconds, optionalEnv } from "./config.js";

const memoryStore = globalThis.__telegramNewsMemoryStore || new Map();
globalThis.__telegramNewsMemoryStore = memoryStore;

function storageKey(chatId) {
  return `telegram-news:last-card-script:${chatId}`;
}

function redisConfig() {
  const url = optionalEnv("UPSTASH_REDIS_REST_URL");
  const token = optionalEnv("UPSTASH_REDIS_REST_TOKEN");
  return { url: url.replace(/\/$/, ""), token };
}

export function hasPersistentCardScriptStorage() {
  const { url, token } = redisConfig();
  return Boolean(url && token);
}

export async function saveLastCardScript(chatId, record) {
  const key = storageKey(chatId);
  const value = JSON.stringify({
    ...record,
    createdAt: new Date().toISOString()
  });

  memoryStore.set(key, value);

  if (!hasPersistentCardScriptStorage()) {
    return false;
  }

  try {
    await redisCommand(["SET", key, value, "EX", String(cardScriptTtlSeconds())]);
    return true;
  } catch (error) {
    console.error(error);
    return false;
  }
}

export async function loadLastCardScript(chatId) {
  const key = storageKey(chatId);
  const memoryValue = memoryStore.get(key);

  if (memoryValue) {
    return JSON.parse(memoryValue);
  }

  if (!hasPersistentCardScriptStorage()) {
    return null;
  }

  let result = null;

  try {
    result = await redisCommand(["GET", key]);
  } catch (error) {
    console.error(error);
  }

  if (!result) {
    return null;
  }

  memoryStore.set(key, result);
  return JSON.parse(result);
}

async function redisCommand(command) {
  const { url, token } = redisConfig();
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(command)
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Upstash Redis error ${response.status}: ${body}`);
  }

  const payload = await response.json();
  if (payload.error) {
    throw new Error(`Upstash Redis error: ${payload.error}`);
  }

  return payload.result;
}
