"""
Lambda: Device heartbeat API.

POST /api/devices/heartbeat updates device metadata and evaluates the alert
state machine immediately, so gateway failures are reported faster than the
scheduled stale-heartbeat sweep.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from telegram_notify import send_telegram_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sns_client = boto3.client("sns")

DEVICE_STATUS_TABLE = os.environ.get("DEVICE_STATUS_TABLE")
DEVICE_ALERT_TOPIC_ARN = os.environ.get("DEVICE_ALERT_TOPIC_ARN")


def heartbeat_handler(event, context):
    """API Gateway handler for POST /api/devices/heartbeat."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"ok": False, "error": "Invalid JSON body"})

    device_id = body.get("deviceId") or body.get("device_id")
    if not device_id:
        return _response(400, {"ok": False, "error": "Missing deviceId"})

    now = datetime.now(timezone.utc).isoformat()
    incoming_status = (body.get("status") or "online").lower()
    if incoming_status not in {"online", "degraded", "offline"}:
        return _response(400, {"ok": False, "error": "Invalid status"})

    table = dynamodb.Table(DEVICE_STATUS_TABLE)

    try:
        existing = table.get_item(Key={"deviceId": device_id}).get("Item", {})
        decision = evaluate_heartbeat_alert(existing, body, incoming_status)
        item_updates = _build_update_values(
            body=body,
            device_id=device_id,
            status=incoming_status,
            alert_state=decision["alertState"],
            last_seen=now,
        )

        if decision["send_alert"]:
            item_updates["lastAlertAt"] = now
            item_updates["lastAlertErrorKey"] = decision["error_key"]

        _update_device(table, device_id, item_updates)

        if decision["send_alert"]:
            message = _build_alert_message(
                device_id=device_id,
                alert_type=decision["alert_type"],
                alert_state=decision["alertState"],
                last_error=body.get("lastError") or body.get("last_error"),
                camera_device=body.get("cameraDevice") or body.get("camera_device"),
                camera_model=body.get("cameraModel") or body.get("camera_model"),
            )
            _send_alert(message)

        return _response(
            200,
            {
                "ok": True,
                "deviceId": device_id,
                "lastSeenAt": now,
                "alertState": decision["alertState"],
            },
        )

    except ClientError as exc:
        logger.exception("Heartbeat persistence failed: %s", exc)
        return _response(500, {"ok": False, "error": "Internal server error"})


def evaluate_heartbeat_alert(existing: dict, payload: dict, status: str) -> dict:
    """
    Evaluate alert transitions for a heartbeat.

    Rules:
    - online -> degraded/offline: alert
    - degraded -> degraded with same error key: skip
    - degraded -> degraded with different error key: alert
    - degraded/offline -> online: recovery alert
    """
    previous_state = (
        existing.get("alertState")
        or existing.get("alert_state")
        or existing.get("status")
        or "online"
    )
    last_error = payload.get("lastError") or payload.get("last_error") or ""
    error_key = _error_key(status, last_error)

    if status == "online":
        return {
            "alertState": "online",
            "send_alert": previous_state in {"degraded", "offline"},
            "alert_type": "device_recovery",
            "error_key": "",
        }

    if status == "degraded":
        same_error = (
            existing.get("lastAlertErrorKey")
            or existing.get("last_alert_error_key")
        ) == error_key
        return {
            "alertState": "degraded",
            "send_alert": previous_state != "degraded" or not same_error,
            "alert_type": "device_degraded",
            "error_key": error_key,
        }

    same_error = (
        existing.get("lastAlertErrorKey")
        or existing.get("last_alert_error_key")
    ) == error_key
    return {
        "alertState": "offline",
        "send_alert": previous_state != "offline" or not same_error,
        "alert_type": "device_offline",
        "error_key": error_key,
    }


def _error_key(status: str, error: str) -> str:
    normalized = " ".join(error.lower().strip().split()) or status
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{status}:{digest}"


def _build_update_values(
    body: dict,
    device_id: str,
    status: str,
    alert_state: str,
    last_seen: str,
) -> dict:
    capture_interval = body.get("captureIntervalSec", body.get("capture_interval_sec"))
    stats = body.get("stats") if isinstance(body.get("stats"), dict) else {}

    updates = {
        "deviceId": device_id,
        "status": status,
        "alertState": alert_state,
        "lastSeenAt": last_seen,
        "lastHeartbeatAt": last_seen,
        "lastCaptureAt": body.get("lastCaptureAt") or body.get("last_capture_at"),
        "lastError": body.get("lastError") or body.get("last_error"),
        "cameraDevice": body.get("cameraDevice") or body.get("camera_device"),
        "cameraModel": body.get("cameraModel") or body.get("camera_model"),
        "cameraSource": body.get("cameraSource") or body.get("camera_source"),
        "uploads": _decimal_or_none(stats.get("uploads")),
        "errors": _decimal_or_none(stats.get("errors")),
    }

    if capture_interval is not None:
        updates["captureIntervalSec"] = _decimal_or_none(capture_interval)

    return updates


def _decimal_or_none(value):
    if value is None:
        return None
    return Decimal(str(value))


def _update_device(table, device_id: str, values: dict):
    names = {}
    expression_values = {}
    assignments = []
    removals = []

    for key, value in values.items():
        if key == "deviceId":
            continue
        name_key = f"#{key}"
        names[name_key] = key
        if value is None:
            removals.append(name_key)
            continue
        value_key = f":{key}"
        expression_values[value_key] = value
        assignments.append(f"{name_key} = {value_key}")

    expression_parts = []
    if assignments:
        expression_parts.append("SET " + ", ".join(assignments))
    if removals:
        expression_parts.append("REMOVE " + ", ".join(removals))

    kwargs = {
        "Key": {"deviceId": device_id},
        "UpdateExpression": " ".join(expression_parts),
        "ExpressionAttributeNames": names,
    }
    if expression_values:
        kwargs["ExpressionAttributeValues"] = expression_values

    table.update_item(**kwargs)


def _build_alert_message(
    device_id: str,
    alert_type: str,
    alert_state: str,
    last_error: str | None,
    camera_device: str | None,
    camera_model: str | None,
) -> dict:
    subject_by_type = {
        "device_degraded": f"Device Degraded: {device_id}",
        "device_offline": f"Device Offline: {device_id}",
        "device_recovery": f"Device Recovered: {device_id}",
    }
    status_text = alert_state.upper()
    text = (
        f"{subject_by_type.get(alert_type, 'Device Alert')}\n"
        "---------------------\n"
        f"Camera: {device_id}\n"
        f"State: {status_text}\n"
        f"Model: {camera_model or 'Unknown'}\n"
        f"Source: {camera_device or 'Unknown'}\n"
        f"Error: {last_error or 'None'}\n"
    )
    return {
        "type": alert_type,
        "deviceId": device_id,
        "alertState": alert_state,
        "lastError": last_error,
        "subject": subject_by_type.get(alert_type, f"Device Alert: {device_id}"),
        "text_message": text,
    }


def _send_alert(message: dict):
    send_telegram_message(message["text_message"])

    if not DEVICE_ALERT_TOPIC_ARN:
        logger.warning("DEVICE_ALERT_TOPIC_ARN not set; skipping SNS alert")
        return

    sns_client.publish(
        TopicArn=DEVICE_ALERT_TOPIC_ARN,
        Message=json.dumps(message),
        Subject=message["subject"][:100],
    )


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
        },
        "body": json.dumps(body, default=str),
    }
