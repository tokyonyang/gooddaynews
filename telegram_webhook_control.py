import { env } from "./config.js";

const TELEGRAM_LIMIT = 3900;

function apiUrl(method) {
  return `https://api.telegram.org/bot${env("TELEGRAM_BOT_TOKEN")}/${method}`;
}

export function isAllowedChat(chatId) {
  return String(chatId) === String(env("TELEGRAM_CHAT_ID"));
}

export function splitTelegramText(text, limit = TELEGRAM_LIMIT) {
  const chunks = [];
  let current = "";

  for (const paragraph of text.split("\n\n")) {
    const candidate = current ? `${current}\n\n${paragraph}` : paragraph;

    if (candidate.length <= limit) {
      current = candidate;
      continue;
    }

    if (current) {
      chunks.push(current);
    }

    if (paragraph.length <= limit) {
      current = paragraph;
    } else {
      for (let index = 0; index < paragraph.length; index += limit) {
        chunks.push(paragraph.slice(index, index + limit));
      }
      current = "";
    }
  }

  if (current) {
    chunks.push(current);
  }

  return chunks;
}

export async function sendMessage(chatId, text, options = {}) {
  for (const chunk of splitTelegramText(text)) {
    const payload = {
      chat_id: chatId,
      text: chunk,
      link_preview_options: { is_disabled: true }
    };

    if (options.replyToMessageId) {
      payload.reply_to_message_id = options.replyToMessageId;
    }

    await telegramPostJson("sendMessage", payload);
  }
}

export async function sendChatAction(chatId, action) {
  await telegramPostJson("sendChatAction", {
    chat_id: chatId,
    action
  });
}

export async function sendPhoto(chatId, imageBuffer, options = {}) {
  const form = new FormData();
  form.append("chat_id", String(chatId));
  form.append("photo", new Blob([imageBuffer], { type: "image/png" }), "cardnews.png");

  if (options.caption) {
    form.append("caption", options.caption.slice(0, 1024));
  }

  if (options.replyToMessageId) {
    form.append("reply_to_message_id", String(options.replyToMessageId));
  }

  const response = await fetch(apiUrl("sendPhoto"), {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Telegram sendPhoto error ${response.status}: ${body}`);
  }

  return response.json();
}

export async function setWebhook(webhookUrl, secretToken) {
  return telegramPostJson("setWebhook", {
    url: webhookUrl,
    secret_token: secretToken,
    allowed_updates: ["message"]
  });
}

export async function getWebhookInfo() {
  return telegramPostJson("getWebhookInfo", {});
}

async function telegramPostJson(method, payload) {
  const response = await fetch(apiUrl(method), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Telegram ${method} error ${response.status}: ${body}`);
  }

  return response.json();
}
