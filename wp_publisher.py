import os
import re
import base64
from urllib.parse import urlparse, urlunparse

import requests


def wp_auth_header(username: str, app_password: str) -> dict:
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _clean_site_url(raw: str) -> str:
    """WP_SITE_URL을 워드프레스 홈 주소 형태로 정리합니다.

    사용자가 /wp-admin, /wp-json/wp/v2/posts 같은 경로까지 넣어도
    중복 경로가 붙지 않도록 보정합니다.
    """
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return ""

    parsed = urlparse(raw if re.match(r"^https?://", raw, re.I) else f"https://{raw}")
    path = parsed.path or ""

    for marker in ["/wp-json", "/wp-admin", "/wp-login.php"]:
        idx = path.find(marker)
        if idx >= 0:
            path = path[:idx]
            break

    cleaned = parsed._replace(path=path.rstrip("/"), params="", query="", fragment="")
    return urlunparse(cleaned).rstrip("/")


def _posts_endpoints(site: str) -> list[str]:
    explicit = (os.environ.get("WP_API_URL") or "").strip().rstrip("/")
    if explicit:
        return [explicit]

    raw_site = (site or "").strip().rstrip("/")
    if raw_site.endswith("/wp-json/wp/v2/posts"):
        return [raw_site]

    base = _clean_site_url(raw_site)
    if not base:
        return []

    # 일반 REST API 주소 + 고유주소 설정이 꺼진 서버용 fallback 주소
    return [
        f"{base}/wp-json/wp/v2/posts",
        f"{base}/?rest_route=/wp/v2/posts",
    ]


def _response_preview(text: str, limit: int = 220) -> str:
    text = str(text or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _friendly_auth_error(message: str) -> str:
    return (
        "워드프레스 글 작성 권한이 없습니다. "
        "WP_USERNAME 사용자의 역할이 관리자/편집자/글쓴이인지 확인하고, "
        "해당 사용자에서 새 Application Password를 발급해 WP_APP_PASSWORD에 넣어주세요. "
        "보안 플러그인이 REST API 또는 Application Password를 막고 있어도 같은 오류가 날 수 있습니다. "
        f"원문: {message}"
    )


def _raise_wp_error(res: requests.Response, endpoint: str) -> None:
    try:
        data = res.json()
    except Exception:
        data = None

    if isinstance(data, dict):
        code = data.get("code") or "unknown"
        message = data.get("message") or res.reason or ""
        if code == "rest_cannot_create" or res.status_code in {401, 403}:
            detail = _friendly_auth_error(message)
        else:
            detail = f"{code}: {message}"
    else:
        preview = _response_preview(res.text)
        if res.status_code == 404:
            detail = (
                "REST API 주소를 찾지 못했습니다. WP_SITE_URL은 워드프레스 홈 주소만 입력하세요. "
                "예: https://gooddaynews.store"
            )
            if preview:
                detail += f" / 응답 요약: {preview}"
        elif res.status_code in {401, 403}:
            detail = _friendly_auth_error(preview or res.reason or "인증 실패")
        else:
            detail = preview or res.reason or "응답 내용을 확인할 수 없습니다."

    raise RuntimeError(f"WordPress post failed: HTTP {res.status_code}. {detail} / endpoint: {endpoint}")


def create_wp_post(article: dict, status: str = None) -> dict:
    site = os.environ.get("WP_SITE_URL", "")
    username = os.environ.get("WP_USERNAME", "")
    password = os.environ.get("WP_APP_PASSWORD", "")
    status = status or os.environ.get("WP_DEFAULT_STATUS", "draft")

    if not site or not username or not password:
        raise RuntimeError("WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD가 필요합니다.")

    endpoints = _posts_endpoints(site)
    if not endpoints:
        raise RuntimeError("WP_SITE_URL을 확인할 수 없습니다.")

    payload = {
        "title": article.get("title") or article.get("keyword") or "제목 없음",
        "content": article.get("html") or "",
        "status": status,
        "slug": article.get("slug"),
        "excerpt": article.get("meta_description", ""),
    }

    last_response = None
    for endpoint in endpoints:
        res = requests.post(endpoint, headers=wp_auth_header(username, password), json=payload, timeout=30)
        if res.status_code < 400:
            return res.json()
        last_response = (res, endpoint)
        # 첫 번째 기본 주소가 404일 때만 fallback 주소를 시도합니다.
        if res.status_code != 404:
            break

    res, endpoint = last_response
    _raise_wp_error(res, endpoint)
