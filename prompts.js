import { env, imageModel, textModel } from "./config.js";

const OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses";

export async function createTextResponse(input, options = {}) {
  const payload = {
    model: options.model || textModel(),
    input
  };

  if (options.instructions) {
    payload.instructions = options.instructions;
  }

  return createResponse(payload);
}

export async function createImageResponse(input, options = {}) {
  return createResponse({
    model: options.model || imageModel(),
    input,
    tools: [{ type: "image_generation" }]
  });
}

async function createResponse(payload) {
  const response = await fetch(OPENAI_RESPONSES_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env("OPENAI_API_KEY")}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`OpenAI API error ${response.status}: ${body}`);
  }

  return response.json();
}

export function getOutputText(response) {
  if (typeof response.output_text === "string") {
    return response.output_text.trim();
  }

  const parts = [];

  for (const item of response.output || []) {
    if (item.type !== "message") {
      continue;
    }

    for (const content of item.content || []) {
      if (content.type === "output_text" && content.text) {
        parts.push(content.text);
      }
    }
  }

  return parts.join("\n").trim();
}

export function getGeneratedImageBase64(response) {
  for (const item of response.output || []) {
    if (item.type === "image_generation_call" && item.result) {
      return item.result;
    }
  }

  return "";
}

export function parseJsonObject(text) {
  const trimmed = text.trim();

  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/\{[\s\S]*\}/);
    if (!match) {
      throw new Error("OpenAI response did not include a JSON object.");
    }
    return JSON.parse(match[0]);
  }
}
