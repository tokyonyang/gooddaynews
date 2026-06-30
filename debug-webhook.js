import { env, optionalEnv } from "../lib/config.js";
import { safeErrorMessage } from "../lib/errors.js";
import { getWebhookInfo } from "../lib/telegram.js";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const secret = url.searchParams.get("secret");

    if (secret !== env("SETUP_SECRET")) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    const webhookInfo = await getWebhookInfo();

    return Response.json({
      ok: true,
      env: {
        hasOpenAiKey: Boolean(optionalEnv("OPENAI_API_KEY")),
        hasTelegramBotToken: Boolean(optionalEnv("TELEGRAM_BOT_TOKEN")),
        hasTelegramChatId: Boolean(optionalEnv("TELEGRAM_CHAT_ID")),
        hasTelegramWebhookSecret: Boolean(optionalEnv("TELEGRAM_WEBHOOK_SECRET")),
        textModel: optionalEnv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
        imageModel: optionalEnv("OPENAI_IMAGE_MODEL", "gpt-4.1-mini")
      },
      telegram: webhookInfo
    });
  } catch (error) {
    console.error(error);

    return Response.json(
      {
        ok: false,
        error: "debug_webhook_failed",
        message: safeErrorMessage(error)
      },
      { status: 500 }
    );
  }
}
