"""
Lambda: Generate Pre-signed URL
Generates time-limited S3 pre-signed URLs for uploading and reading images.

API: POST /api/presigned-url
Body: { "deviceId": "cam-01", "timestamp": "2024-05-28T10:15:30Z" }

API: GET /api/image-url?key=s3://bucket/path/to/image.jpg
"""

import json
import os
import logging
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

RAW_BUCKET = os.environ.get("RAW_BUCKET", "home-security-raw")
THUMB_BUCKET = os.environ.get("THUMB_BUCKET", "home-security-thumb")
PRESIGNED_URL_EXPIRY = int(os.environ.get("PRESIGNED_URL_EXPIRY", "300"))


def lambda_handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "GET":
        return _handle_image_url(event)
    if method and method != "POST":
        return _response(405, {"error": "Method not allowed"})

    return _handle_upload_url(event)


def _handle_upload_url(event):
    """
    Generate a pre-signed PUT URL for image upload.
    
    The edge device calls this endpoint to get a temporary URL
    that allows uploading directly to S3 without AWS credentials.
    """
    try:
        # Parse request body
        body = json.loads(event.get("body", "{}"))
        device_id = body.get("deviceId")
        timestamp_str = body.get("timestamp")

        if not device_id:
            return _response(400, {"error": "Missing required field: deviceId"})

        # Generate timestamp if not provided
        if timestamp_str:
            try:
                ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                return _response(400, {"error": "Invalid timestamp format. Use ISO 8601."})
        else:
            ts = datetime.now(timezone.utc)

        # Build S3 key: {deviceId}/{yyyy}/{mm}/{dd}/{timestamp}.jpg
        s3_key = (
            f"{device_id}/"
            f"{ts.strftime('%Y')}/"
            f"{ts.strftime('%m')}/"
            f"{ts.strftime('%d')}/"
            f"{ts.strftime('%H%M%S')}_{ts.strftime('%f')[:3]}.jpg"
        )

        # Generate pre-signed URL
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": RAW_BUCKET,
                "Key": s3_key,
                "ContentType": "image/jpeg",
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

        logger.info(
            "Generated presigned URL: device=%s, key=%s, expiry=%ds",
            device_id,
            s3_key,
            PRESIGNED_URL_EXPIRY,
        )

        return _response(200, {
            "upload_url": presigned_url,
            "s3_key": s3_key,
            "bucket": RAW_BUCKET,
            "expires_in": PRESIGNED_URL_EXPIRY,
        })

    except ClientError as e:
        logger.error("AWS error generating presigned URL: %s", e)
        return _response(500, {"error": "Failed to generate upload URL"})
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return _response(500, {"error": "Internal server error"})


def _handle_image_url(event):
    """Generate a pre-signed GET URL for a raw or thumbnail image."""
    try:
        query = event.get("queryStringParameters") or {}
        requested_key = query.get("key")
        if not requested_key:
            return _response(400, {"error": "Missing required query parameter: key"})

        bucket, key = _parse_allowed_s3_key(requested_key)
        if not bucket or not key:
            return _response(400, {"error": "Image key is not allowed"})

        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

        logger.info(
            "Generated image URL: bucket=%s, key=%s, expiry=%ds",
            bucket,
            key,
            PRESIGNED_URL_EXPIRY,
        )

        return _response(200, {
            "url": presigned_url,
            "expires_in": PRESIGNED_URL_EXPIRY,
        })

    except ClientError as e:
        logger.error("AWS error generating image URL: %s", e)
        return _response(500, {"error": "Failed to generate image URL"})
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return _response(500, {"error": "Internal server error"})


def _parse_allowed_s3_key(value: str) -> tuple[str | None, str | None]:
    decoded = unquote(value)
    allowed_buckets = {RAW_BUCKET, THUMB_BUCKET}

    if decoded.startswith("s3://"):
        parsed = urlparse(decoded)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        bucket = THUMB_BUCKET
        key = decoded.lstrip("/")

    if bucket not in allowed_buckets or not key or ".." in key.split("/"):
        return None, None
    return bucket, key


def _response(status_code: int, body: dict) -> dict:
    """Create an API Gateway-compatible response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
        },
        "body": json.dumps(body),
    }
