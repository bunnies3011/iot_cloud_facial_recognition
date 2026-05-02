"""
Lambda: Process Image
Main image processing pipeline triggered by SQS (S3 ObjectCreated event).

Flow:
    1. Parse SQS event → extract S3 bucket/key
    2. Download image from S3
    3. Call Rekognition (DetectFaces + SearchFacesByImage)
    4. Generate thumbnail → upload to thumbnails bucket
    5. Save detection results to DynamoDB
    6. Publish notification to SNS (if rules match)
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from notification_rules import should_notify, build_notification_message

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns_client = boto3.client("sns")

# Environment variables
RAW_BUCKET = os.environ.get("RAW_BUCKET")
DETECTIONS_TABLE = os.environ.get("DETECTIONS_TABLE")
DEVICE_STATUS_TABLE = os.environ.get("DEVICE_STATUS_TABLE")
NOTIFICATION_TOPIC_ARN = os.environ.get("NOTIFICATION_TOPIC_ARN")
COLLECTION_ID = os.environ.get("REKOGNITION_COLLECTION_ID", "home-security-faces")
DETECTION_TTL_DAYS = int(os.environ.get("DETECTION_TTL_DAYS", "90"))
SYSTEM_UPLOAD_DEVICE_IDS = {
    value.strip()
    for value in os.environ.get("SYSTEM_UPLOAD_DEVICE_IDS", "web-persons,known-persons").split(",")
    if value.strip()
}


def lambda_handler(event, context):
    """
    SQS-triggered handler. Processes each image upload.
    """
    logger.info("Processing %d SQS record(s)", len(event.get("Records", [])))

    for record in event.get("Records", []):
        try:
            _process_record(record)
        except Exception as e:
            logger.exception("Error processing record: %s", e)
            raise  # Re-raise to trigger SQS retry / DLQ

    return {"statusCode": 200, "body": "OK"}


def _process_record(sqs_record: dict):
    """Process a single SQS record (S3 event)."""
    # Parse S3 event from SQS message
    body = json.loads(sqs_record["body"])

    # Handle S3 test events
    if body.get("Event") == "s3:TestEvent":
        logger.info("Skipping S3 test event")
        return

    for s3_record in body.get("Records", []):
        bucket = s3_record["s3"]["bucket"]["name"]
        key = s3_record["s3"]["object"]["key"]
        size = s3_record["s3"]["object"].get("size", 0)

        logger.info("Processing image: s3://%s/%s (%d bytes)", bucket, key, size)

        # Extract device_id and timestamp from key
        # Key format: {deviceId}/{yyyy}/{mm}/{dd}/{timestamp}.jpg
        parts = key.split("/")
        device_id = parts[0] if parts else "unknown"
        if _is_system_upload(device_id):
            logger.info(
                "Skipping system upload: device=%s, key=s3://%s/%s",
                device_id,
                bucket,
                key,
            )
            continue

        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Download image from S3
        image_bytes = _download_image(bucket, key)
        if not image_bytes:
            logger.error("Failed to download image: %s/%s", bucket, key)
            return

        from rekognition_service import get_face_match_result
        from thumbnail_service import generate_and_upload_thumbnail
        from telegram_notify import send_telegram_message

        # Step 2: Rekognition – detect and match faces
        result = get_face_match_result(image_bytes, COLLECTION_ID)
        logger.info(
            "Rekognition result: status=%s, faces=%d, matches=%d",
            result["status"],
            result["face_count"],
            len(result["matches"]),
        )

        # Step 3: Generate thumbnail
        thumbnail_key = generate_and_upload_thumbnail(image_bytes, key)

        # Step 4: Save to DynamoDB
        person_id = None
        confidence = 0.0
        if result["best_match"]:
            person_id = result["best_match"]["external_image_id"]
            confidence = result["best_match"]["similarity"]

        previous_has_person = _get_latest_presence(device_id)
        current_has_person = result["face_count"] > 0

        detection_item = _save_detection(
            device_id=device_id,
            timestamp=timestamp,
            status=result["status"],
            person_id=person_id,
            confidence=confidence,
            face_count=result["face_count"],
            raw_image_key=f"s3://{bucket}/{key}",
            thumbnail_key=(
                f"s3://{os.environ.get('THUMB_BUCKET')}/{thumbnail_key}"
                if thumbnail_key
                else None
            ),
        )

        # Update device last seen
        _update_device_status(device_id, timestamp)

        # Step 5: Check notification rules
        notify, reason = should_notify(
            device_id=device_id,
            status=result["status"],
            confidence=confidence,
            person_id=person_id,
            previous_has_person=previous_has_person,
            current_has_person=current_has_person,
        )

        if notify:
            message = build_notification_message(
                device_id=device_id,
                timestamp=timestamp,
                status=result["status"],
                reason=reason,
                person_id=person_id,
                confidence=confidence,
                thumbnail_key=thumbnail_key,
            )

            if NOTIFICATION_TOPIC_ARN:
                _publish_notification(message)

        logger.info(
            "✅ Processing complete: device=%s, status=%s, previous_has_person=%s, current_has_person=%s, notify=%s (%s)",
            device_id,
            result["status"],
            previous_has_person,
            current_has_person,
            notify,
            reason,
        )


def _download_image(bucket: str, key: str) -> bytes | None:
    """Download image from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        logger.error("S3 download error: %s", e)
        return None


def _save_detection(
    device_id: str,
    timestamp: str,
    status: str,
    person_id: str | None,
    confidence: float,
    face_count: int,
    raw_image_key: str,
    thumbnail_key: str | None,
) -> dict:
    """Save detection result to DynamoDB."""
    table = dynamodb.Table(DETECTIONS_TABLE)

    # Build GSI keys
    person_id_status = f"{person_id or 'unknown'}#{status}"
    date_key = timestamp[:10]  # yyyy-mm-dd

    item = {
        "deviceId": device_id,
        "timestamp": timestamp,
        "status": status,
        "personId": person_id or "unknown",
        "personIdStatus": person_id_status,
        "dateKey": date_key,
        "confidence": Decimal(str(round(confidence, 2))),
        "faceCount": face_count,
        "hasPerson": face_count > 0,
        "rawImageKey": raw_image_key,
        "ttl": int(
            (datetime.now(timezone.utc) + timedelta(days=DETECTION_TTL_DAYS)).timestamp()
        ),
    }

    if thumbnail_key:
        item["thumbnailKey"] = thumbnail_key

    try:
        table.put_item(Item=item)
        logger.info("Detection saved to DynamoDB: %s @ %s", device_id, timestamp)
        return item
    except ClientError as e:
        logger.error("DynamoDB put_item error: %s", e)
        raise


def _get_latest_presence(device_id: str) -> bool | None:
    """Return whether the latest saved event for this device had any person."""
    table = dynamodb.Table(DETECTIONS_TABLE)

    try:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("deviceId").eq(device_id),
            ScanIndexForward=False,
            Limit=1,
        )
    except ClientError as e:
        logger.warning("Failed to query latest detection presence: %s", e)
        return None

    items = response.get("Items", [])
    if not items:
        return None

    return _item_has_person(items[0])


def _item_has_person(item: dict) -> bool:
    if "hasPerson" in item:
        return bool(item["hasPerson"])

    try:
        face_count = int(item.get("faceCount", 0))
    except (TypeError, ValueError):
        face_count = 0

    return item.get("status") != "no_face" and face_count > 0


def _update_device_status(device_id: str, timestamp: str):
    """Update device last seen time in DynamoDB."""
    table = dynamodb.Table(DEVICE_STATUS_TABLE)
    try:
        table.update_item(
            Key={"deviceId": device_id},
            UpdateExpression=(
                "SET #status = :s, alertState = :a, lastSeenAt = :t, lastImageAt = :t "
                "REMOVE lastError, offlineSince"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":s": "online",
                ":a": "online",
                ":t": timestamp,
            },
        )
    except ClientError as e:
        logger.warning("Failed to update device status: %s", e)


def _publish_notification(message: dict):
    """Publish notification to SNS topic."""
    try:
        sns_client.publish(
            TopicArn=NOTIFICATION_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=message.get("subject", "Security Alert")[:100],
            MessageAttributes={
                "type": {
                    "DataType": "String",
                    "StringValue": message.get("type", "detection_alert"),
                },
                "device_id": {
                    "DataType": "String",
                    "StringValue": message.get("device_id", "unknown"),
                },
            },
        )
        logger.info("Notification published to SNS: %s", message.get("subject"))
    except ClientError as e:
        logger.error("SNS publish error: %s", e)


# ============================================================
# Additional handler for Web App API: Query Events
# ============================================================
def query_events_handler(event, context):
    """
    API Gateway handler: GET /api/events
    Query parameters: deviceId, date, limit, lastKey
    """
    try:
        params = event.get("queryStringParameters") or {}
        device_id = params.get("deviceId")
        date_key = params.get("date")
        limit = int(params.get("limit", "50"))
        query_limit = min(max(limit, 1) * 3, 200)

        table = dynamodb.Table(DETECTIONS_TABLE)

        if device_id:
            # Query by device
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("deviceId").eq(device_id),
                ScanIndexForward=False,
                Limit=query_limit,
            )
        elif date_key:
            # Query by date (GSI)
            response = table.query(
                IndexName="GSI-ByTime",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("dateKey").eq(date_key),
                ScanIndexForward=False,
                Limit=query_limit,
            )
        else:
            # Default: today's events
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            response = table.query(
                IndexName="GSI-ByTime",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("dateKey").eq(today),
                ScanIndexForward=False,
                Limit=query_limit,
            )

        items = json.loads(json.dumps(response.get("Items", []), default=_json_default))
        items = _visible_detection_items(items)[:limit]

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "events": items,
                "count": len(items),
            }),
        }

    except Exception as e:
        logger.exception("Error querying events: %s", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal server error"}),
        }


def _json_default(value):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    return str(value)


def _is_system_upload(device_id: str) -> bool:
    return device_id in SYSTEM_UPLOAD_DEVICE_IDS


def _visible_detection_items(items: list[dict]) -> list[dict]:
    return [
        item
        for item in items
        if not _is_system_upload(str(item.get("deviceId", "")))
    ]
