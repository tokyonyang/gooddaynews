import { env } from "../lib/config.js";
import { safeErrorMessage } from "../lib/errors.js";
import { collectKeywordNews } from "../lib/news.js";

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const secret = url.searchParams.get("secret");
    const keyword = url.searchParams.get("q") || "반도체";

    if (secret !== env("SETUP_SECRET")) {
      return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    const sourceText = await collectKeywordNews(keyword);

    return Response.json({
      ok: true,
      keyword,
      hasNews: Boolean(sourceText),
      length: sourceText.length,
      preview: sourceText.slice(0, 1000)
    });
  } catch (error) {
    console.error(error);

    return Response.json(
      {
        ok: false,
        error: "test_news_failed",
        message: safeErrorMessage(error)
      },
      { status: 500 }
    );
  }
}
