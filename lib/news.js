import { XMLParser } from "fast-xml-parser";
import { newsLookbackHours } from "./config.js";

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@_"
});

const MORNING_QUERIES = [
  ["국내 주요 뉴스", "한국 경제 환율 증시 정책 금융"],
  ["경제 & 증시", "코스피 코스닥 반도체 AI 환율 유가 금리"],
  ["국제 뉴스", "미국 고용지표 연준 금리 중국 PMI 세계 경제"],
  ["투자 포인트", "오늘 증시 투자 포인트 외국인 매매 반도체 환율"]
];

const TREND_QUERIES = [
  ["종합", "오늘 주요 뉴스 속보"],
  ["경제", "오늘 경제 이슈 증시 환율 금리"],
  ["정치", "오늘 정치 이슈 정부 국회"],
  ["사회", "오늘 사회 이슈 사건 사고"],
  ["국제", "오늘 국제 이슈 미국 중국"],
  ["산업/기술", "오늘 산업 IT AI 반도체"],
  ["문화/스포츠", "오늘 문화 스포츠 이슈"]
];

function googleNewsRssUrl(query) {
  const encoded = encodeURIComponent(query);
  return `https://news.google.com/rss/search?q=${encoded}&hl=ko&gl=KR&ceid=KR:ko`;
}

function stripHtml(value = "") {
  return String(value)
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function asArray(value) {
  if (!value) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

async function fetchRssItems(query, section = "뉴스") {
  const response = await fetch(googleNewsRssUrl(query), {
    headers: {
      "User-Agent": "telegram-news-vercel/1.0"
    }
  });

  if (!response.ok) {
    throw new Error(`Google News RSS error ${response.status}`);
  }

  const xml = await response.text();
  const parsed = parser.parse(xml);
  const items = asArray(parsed?.rss?.channel?.item);

  return items.map((item) => ({
    section,
    query,
    title: stripHtml(item.title),
    link: item.link || "",
    publishedAt: item.pubDate || "",
    publishedTime: item.pubDate ? Date.parse(item.pubDate) : 0,
    summary: stripHtml(item.description)
  }));
}

function dedupeAndLimit(items, maxTotalItems) {
  const seen = new Set();
  const result = [];

  for (const item of items) {
    const key = item.title.replace(/\s+-\s+[^-]+$/, "");
    if (!item.title || seen.has(key)) {
      continue;
    }

    seen.add(key);
    result.push(item);

    if (result.length >= maxTotalItems) {
      break;
    }
  }

  return result;
}

function preferRecent(items) {
  const cutoff = Date.now() - newsLookbackHours() * 60 * 60 * 1000;
  const recent = items.filter((item) => item.publishedTime && item.publishedTime >= cutoff);
  return recent.length >= 5 ? recent : items;
}

export async function collectMorningNews() {
  const groups = await fetchQueryGroups(MORNING_QUERIES);

  return formatNewsItems(dedupeAndLimit(preferRecent(groups.flat()), 36));
}

export async function collectTrendingNews() {
  const groups = await fetchQueryGroups(TREND_QUERIES);

  return formatNewsItems(dedupeAndLimit(preferRecent(groups.flat()), 56));
}

export async function collectKeywordNews(keyword) {
  const cleanKeyword = keyword.replace(/\s+/g, " ").trim();
  const queries = [
    cleanKeyword,
    `${cleanKeyword} 최신`,
    `${cleanKeyword} 경제`,
    `${cleanKeyword} 증시`,
    `${cleanKeyword} 전망`
  ];

  const groups = await fetchQueryGroups(queries.map((query) => ["키워드 뉴스", query]));

  return formatNewsItems(dedupeAndLimit(preferRecent(groups.flat()), 28));
}

async function fetchQueryGroups(queryPairs) {
  const results = await Promise.allSettled(
    queryPairs.map(([section, query]) => fetchRssItems(query, section))
  );

  const groups = [];

  for (const result of results) {
    if (result.status === "fulfilled") {
      groups.push(result.value);
    } else {
      console.error(result.reason);
    }
  }

  return groups;
}

export function formatNewsItems(items) {
  return items
    .map(
      (item) => [
        `[섹션] ${item.section}`,
        `검색어: ${item.query}`,
        `제목: ${item.title}`,
        `발행: ${item.publishedAt || "발행일 미확인"}`,
        `요약: ${item.summary || "요약 없음"}`,
        `링크: ${item.link}`
      ].join("\n")
    )
    .join("\n\n");
}
