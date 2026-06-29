import { baseUrlFromRequest, env } from "../lib/config.js";
import { safeErrorMessage } from "../lib/errors.js";
import { setWebhook } from "../lib/telegram.js";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const secret = url.searchParams.get("secret");

    if (secret !== env("SETUP_SECRET")) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    const webhookSecret = env("TELEGRAM_WEBHOOK_SECRET");
    validateTelegramWebhookSecret(webhookSecret);

    const webhookUrl = `${baseUrlFromRequest(request)}/api/telegram-webhook`;
    const result = await setWebhook(webhookUrl, webhookSecret);

    return Response.json({
      ok: true,
      webhookUrl,
      telegram: result
    });
  } catch (error) {
    console.error(error);

    return Response.json(
      {
        ok: false,
        error: "setup_webhook_failed",
        message: safeErrorMessage(error),
        checkList: [
          "Vercel Environment Variables에 TELEGRAM_BOT_TOKEN이 있는지 확인하세요.",
          "Vercel Environment Variables에 TELEGRAM_WEBHOOK_SECRET이 있는지 확인하세요.",
          "TELEGRAM_WEBHOOK_SECRET은 영문, 숫자, 밑줄(_), 하이픈(-)만 사용하세요.",
          "TELEGRAM_BOT_TOKEN 값이 BotFather에서 받은 값과 정확히 같은지 확인하세요.",
          "환경변수를 수정했다면 Vercel에서 Redeploy를 다시 실행하세요."
        ]
      },
      { status: 500 }
    );
  }
}

function validateTelegramWebhookSecret(secret) {
  if (!/^[A-Za-z0-9_-]{1,256}$/.test(secret)) {
    throw new Error(
      "Invalid TELEGRAM_WEBHOOK_SECRET. Use only A-Z, a-z, 0-9, underscore(_), or hyphen(-). Do not use symbols like !."
    );
  }
}
