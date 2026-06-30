import os
import json
import re
from pathlib import Path
from seo_utils import make_slug, clean_text


def _strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> dict:
    """Gemini 응답에서 JSON 객체만 안전하게 추출합니다."""
    text = _strip_code_fence(text)

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # 리포트에 너무 긴 원문이 찍히지 않도록 앞부분만 남깁니다.
        preview = clean_text(text)[:300]
        raise ValueError(f"Gemini JSON 파싱 실패: {exc.msg}. 응답 앞부분: {preview}") from exc


def _build_prompt(template_text: str, keyword: str, site_description: str) -> str:
    """프롬프트 템플릿 치환.

    기존 str.format()은 템플릿 내부 JSON 예시의 중괄호까지 포맷 문자열로
    해석해서 KeyError('\n  "title"')를 발생시켰습니다.
    그래서 필요한 자리표시자만 직접 치환합니다.
    """
    return (
        template_text
        .replace("{keyword}", keyword)
        .replace("{site_description}", site_description or "생활 정보 블로그")
    )


def _normalize_article(data: dict, keyword: str) -> dict:
    data = data or {}
    data["keyword"] = keyword
    data["title"] = clean_text(data.get("title") or keyword)
    data["slug"] = data.get("slug") or make_slug(data["title"] or keyword)
    data["meta_description"] = clean_text(data.get("meta_description") or "")
    data["html"] = data.get("html") or ""
    data["tags"] = data.get("tags") if isinstance(data.get("tags"), list) else []
    data["category"] = data.get("category") or "생활정보"
    data["review_checklist"] = data.get("review_checklist") if isinstance(data.get("review_checklist"), list) else []
    return data


def generate_article(keyword: str, site_description: str = "", model: str = None) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 없습니다.")

    model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    template_text = Path("templates/article_prompt.md").read_text(encoding="utf-8")
    prompt = _build_prompt(template_text, keyword, site_description or "생활 정보 블로그")

    from google import genai

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents=prompt)
    data = _extract_json(resp.text or "")
    return _normalize_article(data, keyword)
