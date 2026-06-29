import { env } from "../lib/config.js";
import { safeErrorMessage } from "../lib/errors.js";
import { sendMessage } from "../lib/telegram.js";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const secret = url.searchParams.get("secret");

    if (secret !== env("SETUP_SECRET")) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    await sendMessage(
      env("TELEGRAM_CHAT_ID"),
      "테스트 메시지입니다. Vercel 서버가 텔레그램으로 메시지를 보낼 수 있습니다."
    );

    return Response.json({
      ok: true,
      message: "test message sent"
    });
  } catch (error) {
    console.error(error);

    return Response.json(
      {
        ok: false,
        error: "test_message_failed",
        message: safeErrorMessage(error),
        checkList: [
          "TELEGRAM_BOT_TOKEN이 BotFather 토큰과 정확히 같은지 확인하세요.",
          "TELEGRAM_CHAT_ID가 내 채팅방 ID와 맞는지 확인하세요.",
          "봇에게 먼저 /start를 보냈는지 확인하세요.",
          "환경변수를 수정했다면 Vercel에서 Redeploy를 다시 실행하세요."
        ]
      },
      { status: 500 }
    );
  }
}
