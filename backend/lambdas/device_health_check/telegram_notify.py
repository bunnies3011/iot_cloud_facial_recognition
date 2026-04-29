"""
Lightweight Telegram notification helper for device health alerts.
"""

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TIMEOUT_SECONDS = int(os.environ.get("TELEGRAM_TIMEOUT_SECONDS", "5"))


def send_telegram_message(text: str) -> bool:
    """Send a Telegram message, returning False if Telegram is not configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram env vars not configured; skipping device alert")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{urllib.parse.quote(TELEGRAM_BOT_TOKEN)}/sendMessage"
    )
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TELEGRAM_TIMEOUT_SECONDS) as response:
            if 200 <= response.status < 300:
                logger.info("Direct Telegram device alert sent")
                return True
            logger.warning("Telegram returned HTTP %s", response.status)
    except Exception as exc:
        logger.warning("Telegram device alert failed: %s", exc)

    return False
