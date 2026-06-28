"""Set, inspect, or delete the Telegram webhook for the Vercel endpoint.

Examples:
  python scripts/telegram_webhook_control.py --action set --url https://your-project.vercel.app
  python scripts/telegram_webhook_control.py --action info
  python scripts/telegram_webhook_control.py --action delete
"""

import argparse
import os
import sys
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv()


def _bot_api(method: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return f"https://api.telegram.org/bot{token}/{method}"


def _normalize_webhook_url(raw: str, path: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise RuntimeError("Webhook URL is required. Set TELEGRAM_WEBHOOK_URL or pass --url")
    if not raw.startswith(("http://", "https://")):
        raise RuntimeError("Webhook URL must start with http:// or https://")
    if raw.rstrip("/").endswith(path.strip("/")):
        return raw.rstrip("/")
    return urljoin(raw.rstrip("/") + "/", path.lstrip("/"))


def _post(method: str, payload: dict | None = None) -> dict:
    resp = requests.post(_bot_api(method), json=payload or {}, timeout=30)
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or not data.get("ok", False):
        raise RuntimeError(f"Telegram {method} failed: {resp.status_code} {data}")
    return data


def _get(method: str) -> dict:
    resp = requests.get(_bot_api(method), timeout=30)
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400 or not data.get("ok", False):
        raise RuntimeError(f"Telegram {method} failed: {resp.status_code} {data}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["set", "info", "delete"], default=os.environ.get("TELEGRAM_WEBHOOK_ACTION", "set"))
    parser.add_argument("--url", default=os.environ.get("TELEGRAM_WEBHOOK_URL", ""), help="Vercel project URL or full webhook URL")
    parser.add_argument("--path", default=os.environ.get("TELEGRAM_WEBHOOK_PATH", "/api/telegram_webhook"))
    parser.add_argument("--drop-pending-updates", default=os.environ.get("TELEGRAM_WEBHOOK_DROP_PENDING", "true"))
    args = parser.parse_args()

    if args.action == "info":
        print(_get("getWebhookInfo"))
        return

    if args.action == "delete":
        payload = {
            "drop_pending_updates": str(args.drop_pending_updates).lower() in {"1", "true", "yes", "y", "on"},
        }
        print(_post("deleteWebhook", payload))
        return

    url = _normalize_webhook_url(args.url, args.path)
    payload = {
        "url": url,
        "allowed_updates": ["message", "channel_post", "edited_message", "edited_channel_post"],
        "drop_pending_updates": str(args.drop_pending_updates).lower() in {"1", "true", "yes", "y", "on"},
    }

    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if secret:
        payload["secret_token"] = secret

    max_connections = os.environ.get("TELEGRAM_WEBHOOK_MAX_CONNECTIONS", "").strip()
    if max_connections.isdigit():
        payload["max_connections"] = max(1, min(int(max_connections), 100))

    print(_post("setWebhook", payload))
    print(_get("getWebhookInfo"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
