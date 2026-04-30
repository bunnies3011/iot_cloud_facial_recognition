"""
Notification Rules
Determines whether a detection event should trigger a notification.
Implements presence-transition logic and cooldown to prevent notification spam.
"""

import os
import time
import logging

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
    previous_has_person: bool | None = None,
    current_has_person: bool | None = None,
) -> tuple[bool, str]:
    """
    Determine if a notification should be sent.

    Rules:
        1. Person-present → no-person transition → NOTIFY
        2. No-person → person-present transition → NOTIFY
        3. Person-present → person-present transition → no notification
        4. No-person → no-person transition → no notification
        5. Cooldown: skip if last same-transition notification was too recent

    Args:
        device_id: Camera device ID.
        status: "known", "unknown", or "no_face".
        confidence: Match confidence (0-100).
        person_id: Matched person ID (if known).
        confidence_threshold: Minimum confidence for "known" to skip notification.
        previous_has_person: Whether the previous event for this device had any face.
        current_has_person: Whether the current event has any face.

    Returns:
        Tuple of (should_notify: bool, reason: str).
    """
    del confidence_threshold

    if current_has_person is None:
        current_has_person = status != "no_face"

    if previous_has_person is None:
        return False, "No previous presence state"

    if not previous_has_person and current_has_person:
        return _notify_with_cooldown(
            device_id=device_id,
            transition="person_appeared",
            success_reason=f"Person detected ({status})",
        )

    if previous_has_person and current_has_person:
        return False, "Person still present"

    if not previous_has_person and not current_has_person:
        return False, "No person still detected"

    return _notify_with_cooldown(
        device_id=device_id,
        transition="person_left",
        success_reason="Person no longer detected",
    )


def _notify_with_cooldown(
    device_id: str,
    transition: str,
    success_reason: str,
) -> tuple[bool, str]:
    # Check cooldown
    now = time.time()
    cooldown_key = f"{device_id}:{transition}"
    last_time = _last_notification_time.get(cooldown_key, 0)
    if now - last_time < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last_time))
        return False, f"Cooldown active ({remaining}s remaining)"

    _last_notification_time[cooldown_key] = now
    return True, success_reason


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
