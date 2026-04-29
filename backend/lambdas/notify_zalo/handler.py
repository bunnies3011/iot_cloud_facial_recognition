"""
Lambda: Notify via Zalo OA
Triggered by SNS. Sends detection alerts to Zalo Official Account followers.

Zalo OA API v3: https://developers.zalo.me/docs/official-account
"""

import json
import os
import logging

import boto3
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()
s3_client = boto3.client("s3")

ZALO_OA_ACCESS_TOKEN = os.environ.get("ZALO_OA_ACCESS_TOKEN", "")
ZALO_API_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"
THUMB_BUCKET = os.environ.get("THUMB_BUCKET", "")


def lambda_handler(event, context):
    """
    SNS-triggered handler. Sends messages to Zalo OA.
    """
    for record in event.get("Records", []):
        try:
            message = json.loads(record["Sns"]["Message"])
            _process_notification(message)
        except Exception as e:
            logger.exception("Error processing Zalo notification: %s", e)

    return {"statusCode": 200}


def _process_notification(message: dict):
    """Process and send a notification via Zalo OA."""
    alert_type = message.get("type", "detection_alert")
    device_id = message.get("device_id", "unknown")
    timestamp = message.get("timestamp", "")
    status = message.get("status", "")
    reason = message.get("reason", "")
    confidence = message.get("confidence", 0)
    text_message = message.get("text_message", "")
    thumbnail_key = message.get("thumbnail_key")

    logger.info(
        "Sending Zalo notification: device=%s, type=%s, status=%s",
        device_id,
        alert_type,
        status,
    )

    if not ZALO_OA_ACCESS_TOKEN:
        logger.warning("ZALO_OA_ACCESS_TOKEN not set — skipping Zalo notification")
        return

    # Generate thumbnail URL if available
    thumbnail_url = None
    if thumbnail_key and THUMB_BUCKET:
        thumbnail_url = _get_presigned_thumb_url(thumbnail_key)

    # Build Zalo message payload
    if thumbnail_url:
        _send_zalo_image_message(text_message, thumbnail_url)
    else:
        _send_zalo_text_message(text_message)


def _send_zalo_text_message(text: str):
    """Send a text message via Zalo OA broadcast."""
    # Note: In production, you'd send to specific user_id
    # This is a simplified example using the CS message API
    payload = {
        "recipient": {"user_id": "ALL"},  # Replace with actual user management
        "message": {"text": text},
    }

    try:
        response = http.request(
            "POST",
            ZALO_API_URL,
            headers={
                "Content-Type": "application/json",
                "access_token": ZALO_OA_ACCESS_TOKEN,
            },
            body=json.dumps(payload),
        )

        result = json.loads(response.data.decode("utf-8"))
        if result.get("error") == 0:
            logger.info("Zalo message sent successfully")
        else:
            logger.warning("Zalo API error: %s", result)

    except Exception as e:
        logger.error("Failed to send Zalo message: %s", e)


def _send_zalo_image_message(text: str, image_url: str):
    """Send an image message with caption via Zalo OA."""
    payload = {
        "recipient": {"user_id": "ALL"},
        "message": {
            "text": text,
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "media",
                    "elements": [
                        {
                            "media_type": "image",
                            "url": image_url,
                        }
                    ],
                },
            },
        },
    }

    try:
        response = http.request(
            "POST",
            ZALO_API_URL,
            headers={
                "Content-Type": "application/json",
                "access_token": ZALO_OA_ACCESS_TOKEN,
            },
            body=json.dumps(payload),
        )

        result = json.loads(response.data.decode("utf-8"))
        if result.get("error") == 0:
            logger.info("Zalo image message sent successfully")
        else:
            logger.warning("Zalo API error: %s", result)

    except Exception as e:
        logger.error("Failed to send Zalo image message: %s", e)


def _get_presigned_thumb_url(thumbnail_key: str) -> str | None:
    """Generate a pre-signed GET URL for the thumbnail."""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": THUMB_BUCKET, "Key": thumbnail_key},
            ExpiresIn=3600,
        )
        return url
    except Exception as e:
        logger.warning("Failed to generate thumbnail URL: %s", e)
        return None
