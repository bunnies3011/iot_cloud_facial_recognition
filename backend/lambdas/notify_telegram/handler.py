"""
Lambda: Notify via Telegram Bot
Triggered by SNS. Sends detection alerts with photos to a Telegram chat.

Telegram Bot API: https://core.telegram.org/bots/api
"""

import json
import os
import logging
import io

import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()
s3_client = boto3.client("s3")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
THUMB_BUCKET = os.environ.get("THUMB_BUCKET", "")


def lambda_handler(event, context):
    """SNS-triggered handler. Sends messages to Telegram."""
    for record in event.get("Records", []):
        try:
            message = json.loads(record["Sns"]["Message"])
            _process_notification(message)
        except Exception as e:
            logger.exception("Error processing Telegram notification: %s", e)

    return {"statusCode": 200}


def _process_notification(message: dict):
    """Process and send a notification via Telegram Bot."""
    text_message = message.get("text_message", "")
    thumbnail_key = message.get("thumbnail_key")
    device_id = message.get("device_id", "unknown")
    status = message.get("status", "")

    logger.info(
        "Sending Telegram notification: device=%s, status=%s",
        device_id,
        status,
    )

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping"
        )
        return

    # Try to send photo with caption if thumbnail is available
    if thumbnail_key and THUMB_BUCKET:
        thumb_bytes = _download_thumbnail(thumbnail_key)
        if thumb_bytes:
            _send_photo(thumb_bytes, text_message)
            return

    # Fallback to text-only message
    _send_text(text_message)


def _send_text(text: str):
    """Send a text message to Telegram."""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        response = http.request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload),
        )

        result = json.loads(response.data.decode("utf-8"))
        if result.get("ok"):
            logger.info("Telegram message sent successfully")
        else:
            logger.warning("Telegram API error: %s", result)

    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)


def _send_photo(photo_bytes: bytes, caption: str):
    """Send a photo with caption to Telegram using multipart form data."""
    url = f"{TELEGRAM_API_URL}/sendPhoto"

    # Build multipart form data
    fields = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption[:1024],  # Telegram caption limit
        "photo": ("alert.jpg", photo_bytes, "image/jpeg"),
    }

    try:
        response = http.request(
            "POST",
            url,
            fields=fields,
        )

        result = json.loads(response.data.decode("utf-8"))
        if result.get("ok"):
            logger.info("Telegram photo sent successfully")
        else:
            logger.warning("Telegram API error: %s", result)
            # Fallback to text
            _send_text(caption)

    except Exception as e:
        logger.error("Failed to send Telegram photo: %s", e)
        _send_text(caption)


def _download_thumbnail(thumbnail_key: str) -> bytes | None:
    """Download thumbnail from S3."""
    try:
        response = s3_client.get_object(Bucket=THUMB_BUCKET, Key=thumbnail_key)
        return response["Body"].read()
    except Exception as e:
        logger.warning("Failed to download thumbnail: %s", e)
        return None
