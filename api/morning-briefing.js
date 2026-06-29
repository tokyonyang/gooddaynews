import { env } from "../lib/config.js";
import { sendMorningBriefing } from "../lib/handlers.js";

export async function GET(request) {
  const chatId = env("TELEGRAM_CHAT_ID");

  if (!isCronOrManualRequest(request)) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  await sendMorningBriefing(chatId);
  return Response.json({ ok: true });
}

function isCronOrManualRequest(request) {
  const url = new URL(request.url);
  const manualSecret = url.searchParams.get("secret");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && manualSecret === cronSecret) {
    return true;
  }

  const userAgent = request.headers.get("user-agent") || "";
  return userAgent.includes("vercel-cron");
}
