import { waitUntil } from "@vercel/functions";
import { env } from "../lib/config.js";
import { userFacingErrorMessage } from "../lib/errors.js";
import {
  extractCardScriptKeyword,
  extractCardKeyword,
  HELP_MESSAGE,
  isCardScriptRequest,
  isCardNewsRequest,
  isChatIdCommand,
  isHelpCommand,
  isMorningBriefingRequest,
  isTrendRankingRequest,
  normalizeQuestion
} from "../lib/intent.js";
import { sendCardNews, sendCardScript, sendKeywordBriefing, sendMorningBriefing, sendTrendRanking } from "../lib/handlers.js";
import { isAllowedChat, sendMessage } from "../lib/telegram.js";

export async function POST(request) {
  const secretHeader = request.headers.get("x-telegram-bot-api-secret-token");

  if (secretHeader !== env("TELEGRAM_WEBHOOK_SECRET")) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const update = await request.json();
  waitUntil(handleTelegramUpdate(update));

  return Response.json({ ok: true });
}

export async function GET() {
  return Response.json({
    ok: true,
    message: "Telegram webhook endpoint is ready. Use POST from Telegram."
  });
}

async function handleTelegramUpdate(update) {
  const message = update.message;
  const text = normalizeQuestion(message?.text || "");
  const chatId = message?.chat?.id;
  const messageId = message?.message_id;

  if (!text || !chatId || !messageId) {
    console.log("Ignored update without text/chat/message id");
    return;
  }

  if (isChatIdCommand(text)) {
    await sendMessage(chatId, `현재 텔레그램 chat_id는 ${chatId} 입니다. 이 값을 Vercel의 TELEGRAM_CHAT_ID에 넣어주세요.`, {
      replyToMessageId: messageId
    });
    return;
  }

  if (!isAllowedChat(chatId)) {
    console.log(`Ignored message from unauthorized chat: ${chatId}`);
    return;
  }

  try {
    if (isHelpCommand(text)) {
      await sendMessage(chatId, HELP_MESSAGE, { replyToMessageId: messageId });
      return;
    }

    if (isMorningBriefingRequest(text)) {
      await sendMorningBriefing(chatId, messageId);
      return;
    }

    if (isTrendRankingRequest(text)) {
      await sendTrendRanking(chatId, messageId);
      return;
    }

    if (isCardScriptRequest(text)) {
      const keyword = extractCardScriptKeyword(text);
      await sendCardScript(chatId, keyword, messageId);
      return;
    }

    if (isCardNewsRequest(text)) {
      const keyword = extractCardKeyword(text);

      if (!keyword) {
        await sendMessage(chatId, "카드뉴스로 만들 키워드를 같이 보내주세요. 예: 반도체 카드뉴스 만들어줘", {
          replyToMessageId: messageId
        });
        return;
      }

      await sendMessage(chatId, `'${keyword}' 카드뉴스를 만들고 있어요. 관련 자료를 먼저 확인한 뒤 이미지로 보내드릴게요.`, {
        replyToMessageId: messageId
      });
      await sendCardNews(chatId, keyword, messageId);
      return;
    }

    if (text.length > 120) {
      await sendMessage(chatId, "질문이 조금 길어요. 핵심 키워드나 한 문장 질문으로 다시 보내주세요.", {
        replyToMessageId: messageId
      });
      return;
    }

    await sendKeywordBriefing(chatId, text, messageId);
  } catch (error) {
    console.error(error);
    await sendMessage(
      chatId,
      [
        "처리 중 오류가 발생했습니다.",
        "",
        userFacingErrorMessage(error),
        "",
        "Vercel에서 /api/test-openai 또는 /api/test-news 진단 주소를 확인해보세요."
      ].join("\n"),
      {
        replyToMessageId: messageId
      }
    );
  }
}
