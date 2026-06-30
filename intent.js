import { collectKeywordNews, collectMorningNews, collectTrendingNews } from "./news.js";
import { createImageResponse, createTextResponse, getGeneratedImageBase64, getOutputText, parseJsonObject } from "./openai.js";
import {
  buildCardImagePrompt,
  buildCardScriptPrompt,
  buildKeywordBriefingPrompt,
  buildMorningBriefingPrompt,
  buildTrendRankingPrompt,
  formatCardScriptMessage
} from "./prompts.js";
import { loadLastCardScript, saveLastCardScript } from "./storage.js";
import { sendChatAction, sendMessage, sendPhoto } from "./telegram.js";

export async function sendMorningBriefing(chatId, replyToMessageId = undefined) {
  await sendChatAction(chatId, "typing");

  const sourceText = await collectMorningNews();
  if (!sourceText) {
    await sendMessage(chatId, "오늘 모닝 브리핑용 뉴스 후보를 찾지 못했습니다.", {
      replyToMessageId
    });
    return;
  }

  const response = await createTextResponse(buildMorningBriefingPrompt(sourceText));
  const briefing = getOutputText(response);

  await sendMessage(chatId, briefing, { replyToMessageId });
}

export async function sendKeywordBriefing(chatId, keyword, replyToMessageId = undefined) {
  await sendChatAction(chatId, "typing");

  const sourceText = await collectKeywordNews(keyword);
  if (!sourceText) {
    await sendMessage(chatId, `'${keyword}' 관련 최신 기사 후보를 찾지 못했습니다. 키워드를 조금 다르게 보내주세요.`, {
      replyToMessageId
    });
    return;
  }

  const response = await createTextResponse(buildKeywordBriefingPrompt(keyword, sourceText));
  const answer = getOutputText(response);

  await sendMessage(chatId, answer, { replyToMessageId });
}

export async function sendTrendRanking(chatId, replyToMessageId = undefined) {
  await sendChatAction(chatId, "typing");

  const sourceText = await collectTrendingNews();
  if (!sourceText) {
    await sendMessage(chatId, "지금 뜨는 이슈를 뽑을 뉴스 후보를 찾지 못했습니다.", {
      replyToMessageId
    });
    return;
  }

  const response = await createTextResponse(buildTrendRankingPrompt(sourceText));
  const ranking = getOutputText(response);

  await sendMessage(chatId, ranking, { replyToMessageId });
}

export async function sendCardScript(chatId, keyword, replyToMessageId = undefined) {
  await sendChatAction(chatId, "typing");

  if (!keyword) {
    const storedRecord = await loadLastCardScript(chatId);

    if (storedRecord?.cardScript) {
      await sendMessage(
        chatId,
        formatCardScriptMessage(storedRecord.keyword || "최근 카드뉴스", storedRecord.cardScript, {
          fromStorage: true
        }),
        { replyToMessageId }
      );
      return;
    }

    await sendMessage(
      chatId,
      "저장된 카드뉴스 스크립트를 찾지 못했습니다. 키워드를 같이 보내주세요. 예: 반도체 카드뉴스 스크립트",
      { replyToMessageId }
    );
    return;
  }

  try {
    const cardScript = await createAndSaveCardScript(chatId, keyword);
    await sendMessage(chatId, formatCardScriptMessage(keyword, cardScript), {
      replyToMessageId
    });
  } catch (error) {
    console.error(error);
    await sendMessage(chatId, `'${keyword}' 카드뉴스 제작 스크립트를 만들지 못했습니다. 키워드를 조금 다르게 보내주세요.`, {
      replyToMessageId
    });
  }
}

export async function sendCardNews(chatId, keyword, replyToMessageId = undefined) {
  await sendChatAction(chatId, "upload_photo");

  let cardScript;

  try {
    cardScript = await createAndSaveCardScript(chatId, keyword);
  } catch (error) {
    console.error(error);
    await sendMessage(chatId, `'${keyword}' 카드뉴스 제작 스크립트를 만들지 못했습니다. 키워드를 조금 다르게 보내주세요.`, {
      replyToMessageId
    });
    return;
  }

  let imageBase64 = "";

  try {
    const imageResponse = await createImageResponse(buildCardImagePrompt(cardScript));
    imageBase64 = getGeneratedImageBase64(imageResponse);
  } catch (error) {
    console.error(error);
  }

  if (!imageBase64) {
    await sendMessage(
      chatId,
      [
        "카드뉴스 이미지 생성 중 문제가 생겼습니다. 대신 제작 스크립트를 먼저 보내드립니다.",
        "",
        formatCardScriptMessage(keyword, cardScript)
      ].join("\n"),
      { replyToMessageId }
    );
    return;
  }

  const imageBuffer = Buffer.from(imageBase64, "base64");
  const caption = [
    cardScript.caption || `카드뉴스: ${keyword}`,
    "",
    "스크립트가 필요하면 '카드뉴스 스크립트'라고 보내주세요.",
    "",
    ...(cardScript.sources || []).slice(0, 3).map((source) => `- ${source}`)
  ].join("\n");

  await sendPhoto(chatId, imageBuffer, {
    caption,
    replyToMessageId
  });
}

async function createAndSaveCardScript(chatId, keyword) {
  const sourceText = await collectKeywordNews(keyword);
  if (!sourceText) {
    throw new Error(`No card news source found for keyword: ${keyword}`);
  }

  const scriptResponse = await createTextResponse(buildCardScriptPrompt(keyword, sourceText));
  const scriptText = getOutputText(scriptResponse);
  const cardScript = parseJsonObject(scriptText);

  await saveLastCardScript(chatId, {
    keyword,
    cardScript
  });

  return cardScript;
}
