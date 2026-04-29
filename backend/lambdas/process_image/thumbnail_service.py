"""
Thumbnail Service
Generates resized thumbnail images and uploads them to S3.
"""

import io
import os
import logging

from PIL import Image
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

s3_client = boto3.client("s3")

THUMB_BUCKET = os.environ.get("THUMB_BUCKET", "home-security-thumb")
THUMBNAIL_SIZE = int(os.environ.get("THUMBNAIL_SIZE", "200"))


def generate_and_upload_thumbnail(
    image_bytes: bytes,
    raw_s3_key: str,
    thumb_bucket: str | None = None,
    size: int | None = None,
) -> str | None:
    """
    Generate a thumbnail from the original image and upload to S3.

    Args:
        image_bytes: Original image bytes.
        raw_s3_key: S3 key of the raw image (used to derive thumbnail key).
        thumb_bucket: Override thumbnail bucket name.
        size: Override thumbnail max dimension.

    Returns:
        Thumbnail S3 key on success, None on failure.
    """
    bucket = thumb_bucket or THUMB_BUCKET
    max_size = size or THUMBNAIL_SIZE

    try:
        # Generate thumbnail
        thumb_bytes = _create_thumbnail(image_bytes, max_size)

        # Derive thumbnail key from raw key
        # raw: {deviceId}/{yyyy}/{mm}/{dd}/{filename}.jpg
        # thumb: {deviceId}/{yyyy}/{mm}/{dd}/{filename}_thumb.jpg
        base, ext = os.path.splitext(raw_s3_key)
        thumb_key = f"{base}_thumb{ext}"

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=thumb_key,
            Body=thumb_bytes,
            ContentType="image/jpeg",
        )

        logger.info(
            "Thumbnail uploaded: s3://%s/%s (%d bytes)",
            bucket,
            thumb_key,
            len(thumb_bytes),
        )
        return thumb_key

    except ClientError as e:
        logger.error("S3 upload error for thumbnail: %s", e)
        return None
    except Exception as e:
        logger.error("Thumbnail generation error: %s", e)
        return None


def _create_thumbnail(image_bytes: bytes, max_size: int) -> bytes:
    """
    Resize image to thumbnail.

    Args:
        image_bytes: Original image bytes.
        max_size: Maximum dimension (width or height).

    Returns:
        Thumbnail as JPEG bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if needed (handle RGBA, P, etc.)
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Resize maintaining aspect ratio
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Encode to JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80, optimize=True)
    buffer.seek(0)

    logger.debug(
        "Thumbnail created: %dx%d → %dx%d (%d bytes)",
        img.size[0],
        img.size[1],
        img.size[0],
        img.size[1],
        buffer.getbuffer().nbytes,
    )

    return buffer.read()
