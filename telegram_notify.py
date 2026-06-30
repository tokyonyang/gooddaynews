import os
import html
import requests


TELEGRAM_SAFE_LIMIT = 3800


def clean_telegram_text(text: str) -> str:
    """실수로 이스케이프된 줄바꿈/따옴표를 텔레그램 표시용으로 복구합니다."""
    return (
        str(text or "")
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace('\\"', '"')
    )


def html_escape(text: str) -> str:
    return html.escape(str(text or ""), quote=False)


def split_long_text(text: str, limit: int = TELEGRAM_SAFE_LIMIT) -> list[str]:
    """Telegram sendMessage 제한(4096자)을 피하기 위해 긴 글을 안전하게 분할합니다."""
    text = clean_telegram_text(text).strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        piece = paragraph.strip()
        if not piece:
            continue

        # 문단 하나가 너무 길면 줄 단위/문자 단위로 추가 분할합니다.
        if len(piece) > limit:
            if current:
                chunks.append(current.strip())
                current = ""
            while len(piece) > limit:
                split_at = piece.rfind("\n", 0, limit)
                if split_at < int(limit * 0.5):
                    split_at = piece.rfind(" ", 0, limit)
                if split_at < int(limit * 0.5):
                    split_at = limit
                chunks.append(piece[:split_at].strip())
                piece = piece[split_at:].strip()
            if piece:
                current = piece
            continue

        candidate = f"{current}\n\n{piece}" if current else piece
        if len(candidate) > limit:
            chunks.append(current.strip())
            current = piece
        else:
            current = candidate

    if current:
        chunks.append(current.strip())
    return chunks


def send_telegram(text: str, parse_mode: str | None = "HTML"):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[INFO] Telegram secrets not set. Skip.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": clean_telegram_text(text),
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    r = requests.post(url, json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram failed: {r.status_code} {r.text[:300]}")


def send_telegram_long(text: str, parse_mode: str | None = None):
    """긴 글 초안을 여러 메시지로 나눠 보냅니다. 기본은 plain text입니다."""
    chunks = split_long_text(text)
    total = len(chunks)
    for idx, chunk in enumerate(chunks, 1):
        suffix = f"\n\n({idx}/{total})" if total > 1 else ""
        send_telegram(f"{chunk}{suffix}", parse_mode=parse_mode)


def _make_link_buttons(articles: list[dict], limit: int | None = None) -> list[list[dict]]:
    """Telegram inline keyboard URL 버튼을 생성합니다."""
    limit = limit or int(os.environ.get("TELEGRAM_LINK_BUTTON_LIMIT", "8") or 8)
    rows: list[list[dict]] = []
    for idx, article in enumerate((articles or [])[:limit], 1):
        url = str(article.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        title = clean_telegram_text(article.get("title") or f"기사 {idx}").replace("\n", " ").strip()
        rows.append([{"text": f"🔗 {idx}. {title[:34]}", "url": url}])
    return rows


def send_telegram_with_buttons(text: str, articles: list[dict], parse_mode: str | None = "HTML", button_limit: int | None = None):
    """본문에는 긴 URL을 노출하지 않고, 기사 링크를 별도 버튼으로 붙여 보냅니다.

    Telegram은 한 메시지당 4096자 제한이 있으므로, 버튼 메시지는 첫 번째 청크에만 붙입니다.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[INFO] Telegram secrets not set. Skip.")
        return

    chunks = split_long_text(text)
    if not chunks:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    buttons = _make_link_buttons(articles, button_limit)

    for idx, chunk in enumerate(chunks, 1):
        suffix = f"\n\n({idx}/{len(chunks)})" if len(chunks) > 1 else ""
        payload = {
            "chat_id": chat_id,
            "text": clean_telegram_text(f"{chunk}{suffix}"),
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if idx == 1 and buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}

        r = requests.post(url, json=payload, timeout=20)
        if r.status_code >= 400:
            raise RuntimeError(f"Telegram failed: {r.status_code} {r.text[:500]}")
