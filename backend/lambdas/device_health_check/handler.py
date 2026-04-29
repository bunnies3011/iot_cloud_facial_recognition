"""
Lambda: Device Health Check

Scheduled health checks promote stale devices through an explicit alert state:
online -> degraded -> offline. Alerts are sent only when the state changes, so
an already-offline camera does not generate duplicate notifications every run.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
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
OFFLINE_THRESHOLD_MINUTES = int(
    os.environ.get("DEVICE_OFFLINE_THRESHOLD_MINUTES", "10")
)
DEGRADED_THRESHOLD_MINUTES = int(
    os.environ.get(
        "DEVICE_DEGRADED_THRESHOLD_MINUTES",
        str(max(1, OFFLINE_THRESHOLD_MINUTES // 2)),
    )
)


def lambda_handler(event, context):
    """EventBridge scheduled handler. Check all device health."""
    logger.info(
        "Running device health check (degraded=%d min, offline=%d min)",
        DEGRADED_THRESHOLD_MINUTES,
        OFFLINE_THRESHOLD_MINUTES,
    )

    table = dynamodb.Table(DEVICE_STATUS_TABLE)
    now = datetime.now(timezone.utc)
    degraded_threshold = now - timedelta(minutes=DEGRADED_THRESHOLD_MINUTES)
    offline_threshold = now - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)

    try:
        response = table.scan()
        devices = response.get("Items", [])

        counts = {"online": 0, "degraded": 0, "offline": 0}
        alerts_sent = 0

        for device in devices:
            device_id = device["deviceId"]
            last_seen = _parse_time(device.get("lastSeenAt"))
            previous_state = (
                device.get("alertState")
                or device.get("alert_state")
                or device.get("status")
                or "online"
            )

            if not last_seen:
                logger.warning("Device %s has no valid lastSeenAt", device_id)
                continue

            if last_seen < offline_threshold:
                next_state = "offline"
            elif last_seen < degraded_threshold:
                next_state = "degraded"
            else:
                next_state = "online"

            counts[next_state] += 1

            if next_state == "offline":
                minutes_offline = int((now - last_seen).total_seconds() / 60)
                error_key = "offline"
                alert_needed = previous_state != "offline"
                _update_device_state(
                    table,
                    device_id,
                    status="offline",
                    alert_state="offline",
                    last_error=f"No heartbeat for {minutes_offline} minutes",
                    last_alert_error_key=(
                        error_key
                        if alert_needed
                        else device.get("lastAlertErrorKey")
                        or device.get("last_alert_error_key")
                    ),
                    last_alert_at=(
                        now.isoformat()
                        if alert_needed
                        else device.get("lastAlertAt") or device.get("last_alert_at")
                    ),
                    extra={"offlineSince": device.get("offlineSince") or now.isoformat()},
                )
                if alert_needed:
                    _send_alert(
                        {
                            "type": "device_offline",
                            "deviceId": device_id,
                            "lastSeenAt": device.get("lastSeenAt", ""),
                            "minutesOffline": minutes_offline,
                            "alertState": "offline",
                        }
                    )
                    alerts_sent += 1
                continue

            if next_state == "degraded":
                minutes_stale = int((now - last_seen).total_seconds() / 60)
                error_key = "stale_heartbeat"
                alert_needed = (
                    previous_state != "degraded"
                    or (device.get("lastAlertErrorKey") or device.get("last_alert_error_key"))
                    != error_key
                )
                _update_device_state(
                    table,
                    device_id,
                    status="degraded",
                    alert_state="degraded",
                    last_error=f"No heartbeat for {minutes_stale} minutes",
                    last_alert_error_key=(
                        error_key
                        if alert_needed
                        else device.get("lastAlertErrorKey")
                        or device.get("last_alert_error_key")
                    ),
                    last_alert_at=(
                        now.isoformat()
                        if alert_needed
                        else device.get("lastAlertAt") or device.get("last_alert_at")
                    ),
                )
                if alert_needed:
                    _send_alert(
                        {
                            "type": "device_degraded",
                            "deviceId": device_id,
                            "lastSeenAt": device.get("lastSeenAt", ""),
                            "minutesOffline": minutes_stale,
                            "alertState": "degraded",
                        }
                    )
                    alerts_sent += 1
                continue

            _update_device_state(
                table,
                device_id,
                status="online",
                alert_state="online",
                last_error=None,
                extra={"offlineSince": None},
            )
            if previous_state in {"degraded", "offline"}:
                _send_alert(
                        {
                            "type": "device_recovery",
                            "deviceId": device_id,
                            "lastSeenAt": device.get("lastSeenAt", ""),
                            "minutesOffline": 0,
                            "alertState": "online",
                        }
                    )
                alerts_sent += 1

        logger.info(
            "Health check complete: %s online, %s degraded, %s offline, %s alerts",
            counts["online"],
            counts["degraded"],
            counts["offline"],
            alerts_sent,
        )

        return {
            "statusCode": 200,
            "body": json.dumps({**counts, "alerts_sent": alerts_sent}),
        }

    except ClientError as exc:
        logger.exception("Health check error: %s", exc)
        raise


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _update_device_state(
    table,
    device_id: str,
    status: str,
    alert_state: str,
    last_error: str | None,
    last_alert_error_key: str | None = None,
    last_alert_at: str | None = None,
    extra: dict | None = None,
):
    values = {
        ":status": status,
        ":alertState": alert_state,
        ":lastError": last_error,
    }
    names = {
        "#status": "status",
        "#alertState": "alertState",
        "#lastError": "lastError",
    }
    assignments = [
        "#status = :status",
        "#alertState = :alertState",
    ]
    removals = []

    if last_error is None:
        removals.append("#lastError")
        values.pop(":lastError")
    else:
        assignments.append("#lastError = :lastError")

    if last_alert_error_key is not None:
        names["#lastAlertErrorKey"] = "lastAlertErrorKey"
        values[":lastAlertErrorKey"] = last_alert_error_key
        assignments.append("#lastAlertErrorKey = :lastAlertErrorKey")

    if last_alert_at is not None:
        names["#lastAlertAt"] = "lastAlertAt"
        values[":lastAlertAt"] = last_alert_at
        assignments.append("#lastAlertAt = :lastAlertAt")

    for key, value in (extra or {}).items():
        attr_name = f"#{key}"
        attr_value = f":{key}"
        names[attr_name] = key
        if value is None:
            removals.append(attr_name)
            continue
        values[attr_value] = value
        assignments.append(f"{attr_name} = {attr_value}")

    expression_parts = ["SET " + ", ".join(assignments)]
    if removals:
        expression_parts.append("REMOVE " + ", ".join(removals))

    kwargs = {
        "Key": {"deviceId": device_id},
        "UpdateExpression": " ".join(expression_parts),
        "ExpressionAttributeNames": names,
    }
    if values:
        kwargs["ExpressionAttributeValues"] = values

    table.update_item(**kwargs)


def _send_alert(device_info: dict):
    """Publish a device state alert to SNS and direct Telegram."""
    message = _build_alert_message(device_info)
    send_telegram_message(message["text_message"])

    if not DEVICE_ALERT_TOPIC_ARN:
        logger.warning("DEVICE_ALERT_TOPIC_ARN not set; skipping SNS alert")
        return

    try:
        sns_client.publish(
            TopicArn=DEVICE_ALERT_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=message["subject"][:100],
        )
        logger.info("Device alert sent for %s", device_info["deviceId"])
    except ClientError as exc:
        logger.error("Failed to publish device alert: %s", exc)


def _build_alert_message(device_info: dict) -> dict:
    alert_type = device_info["type"]
    device_id = device_info["deviceId"]

    if alert_type == "device_recovery":
        subject = f"Device Recovered: {device_id}"
        text = (
            "Device Recovery\n"
            "----------------\n"
            f"Camera: {device_id}\n"
            f"State: ONLINE\n"
            f"Last Seen: {device_info.get('lastSeenAt', '')}\n"
        )
    elif alert_type == "device_degraded":
        subject = f"Device Degraded: {device_id}"
        text = (
            "Device Degraded Alert\n"
            "---------------------\n"
            f"Camera: {device_id}\n"
            f"Last Seen: {device_info.get('lastSeenAt', '')}\n"
            f"Stale For: {device_info.get('minutesOffline', 0)} minutes\n"
            "Check the RTSP stream and network connection.\n"
        )
    else:
        subject = f"Device Offline: {device_id}"
        text = (
            "Device Offline Alert\n"
            "--------------------\n"
            f"Camera: {device_id}\n"
            f"Last Seen: {device_info.get('lastSeenAt', '')}\n"
            f"Offline: {device_info.get('minutesOffline', 0)} minutes\n"
            "Please check the device.\n"
        )

    return {
        "type": alert_type,
        "deviceId": device_id,
        "lastSeenAt": device_info.get("lastSeenAt"),
        "minutesOffline": device_info.get("minutesOffline", 0),
        "alertState": device_info.get("alertState"),
        "subject": subject,
        "text_message": text,
    }


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def query_devices_handler(event, context):
    """API Gateway handler: GET /api/devices."""
    try:
        table = dynamodb.Table(DEVICE_STATUS_TABLE)
        response = table.scan()
        devices = []

        for raw_device in response.get("Items", []):
            device = json.loads(json.dumps(raw_device, default=_json_default))
            alert_state = (
                device.get("alertState")
                or device.get("alert_state")
                or device.get("status", "unknown")
            )
            device["alertState"] = alert_state
            device["isOnline"] = alert_state == "online"
            device.pop("alert_state", None)
            device.pop("last_error", None)
            device.pop("camera_device", None)
            device.pop("camera_model", None)
            device.pop("camera_source", None)
            device.pop("capture_interval_sec", None)
            devices.append(device)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"devices": devices, "count": len(devices)}),
        }

    except Exception as exc:
        logger.exception("Error querying devices: %s", exc)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Internal server error"}),
        }
