"""
Notification Rules
Determines whether a detection event should trigger a notification.
Implements cooldown logic to prevent notification spam.
"""

import os
import time
import logging
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()

# In-memory cooldown tracker (reset on Lambda cold start)
_last_notification_time: dict[str, float] = {}

COOLDOWN_SECONDS = int(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "60"))


def should_notify(
    device_id: str,
    status: str,
    confidence: float,
    person_id: str | None = None,
    confidence_threshold: float = 90.0,
) -> tuple[bool, str]:
    """
    Determine if a notification should be sent.

    Rules:
        1. Unknown person detected → NOTIFY
        2. Known person with low confidence (< threshold) → NOTIFY
        3. Cooldown: skip if last notification for this device was too recent

    Args:
        device_id: Camera device ID.
        status: "known", "unknown", or "no_face".
        confidence: Match confidence (0-100).
        person_id: Matched person ID (if known).
        confidence_threshold: Minimum confidence for "known" to skip notification.

    Returns:
        Tuple of (should_notify: bool, reason: str).
    """
    # No face detected → no notification
    if status == "no_face":
        return False, "No face detected"

    # Check cooldown
    now = time.time()
    last_time = _last_notification_time.get(device_id, 0)
    if now - last_time < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last_time))
        return False, f"Cooldown active ({remaining}s remaining)"

    # Unknown person → always notify
    if status == "unknown":
        _last_notification_time[device_id] = now
        return True, "Unknown person detected"

    # Known person with low confidence → notify
    if status == "known" and confidence < confidence_threshold:
        _last_notification_time[device_id] = now
        return True, f"Low confidence match ({confidence:.1f}% < {confidence_threshold}%)"

    # Known person with high confidence → no notification
    return False, f"Known person '{person_id}' (confidence: {confidence:.1f}%)"


def build_notification_message(
    device_id: str,
    timestamp: str,
    status: str,
    reason: str,
    person_id: str | None = None,
    confidence: float = 0.0,
    thumbnail_key: str | None = None,
) -> dict:
    """
    Build the SNS notification message payload.

    Returns:
        dict suitable for SNS publish.
    """
    emoji = "🚨" if status == "unknown" else "⚠️"

    message = {
        "type": "detection_alert",
        "device_id": device_id,
        "timestamp": timestamp,
        "status": status,
        "reason": reason,
        "person_id": person_id or "unknown",
        "confidence": round(confidence, 1),
        "thumbnail_key": thumbnail_key,
        "subject": f"{emoji} Security Alert: {reason}",
        "text_message": (
            f"{emoji} Home Security Alert\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📷 Camera: {device_id}\n"
            f"🕐 Time: {timestamp}\n"
            f"👤 Status: {status.upper()}\n"
            f"📊 Confidence: {confidence:.1f}%\n"
            f"💡 Reason: {reason}\n"
        ),
    }
    return message
