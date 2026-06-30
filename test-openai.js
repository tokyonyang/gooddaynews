import { env, optionalEnv } from "../lib/config.js";
import { safeErrorMessage } from "../lib/errors.js";
import { createTextResponse, getOutputText } from "../lib/openai.js";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const secret = url.searchParams.get("secret");

    if (secret !== env("SETUP_SECRET")) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    const response = await createTextResponse(
      "한국어로 짧게 'OpenAI 연결 정상'이라고만 답하세요."
    );
    const text = getOutputText(response);

    return Response.json({
      ok: true,
      model: optionalEnv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
      output: text
    });
  } catch (error) {
    console.error(error);

    return Response.json(
      {
        ok: false,
        error: "test_openai_failed",
        message: safeErrorMessage(error),
        checkList: [
          "Vercel Environment Variables의 OPENAI_API_KEY 값을 확인하세요.",
          "OPENAI_TEXT_MODEL을 gpt-4.1-mini로 설정하세요.",
          "환경변수를 수정했다면 Vercel에서 Redeploy를 다시 실행하세요.",
          "OpenAI 계정의 결제/사용량 한도를 확인하세요."
        ]
      },
      { status: 500 }
    );
  }
}
