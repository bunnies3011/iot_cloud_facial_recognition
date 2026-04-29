"""
Image Uploader Module
Handles secure image upload to S3 via pre-signed URLs.
Flow: Request pre-signed URL → Upload image via HTTPS PUT.
"""

import io
import time
import logging
from datetime import datetime, timezone

import cv2
import numpy as np
import requests

from config import UploadConfig, DeviceConfig

logger = logging.getLogger("home-security.uploader")


class ImageUploader:
    """
    Uploads captured images to S3 using pre-signed URLs.
    
    Steps:
        1. Encode frame as JPEG
        2. Request pre-signed URL from API Gateway (POST)
        3. Upload JPEG to S3 via pre-signed URL (PUT)
    """

    def __init__(self, upload_config: UploadConfig, device_config: DeviceConfig):
        self.upload_config = upload_config
        self.device_config = device_config
        self._session = requests.Session()
        self._session.headers.update({
            "x-api-key": upload_config.api_key,
            "Content-Type": "application/json",
        })
        self._upload_count = 0
        self._error_count = 0

        logger.info(
            "ImageUploader initialized (endpoint=%s, device=%s)",
            upload_config.api_endpoint,
            device_config.device_id,
        )

    def upload_frame(
        self,
        frame: np.ndarray,
        jpeg_quality: int = 85,
        timestamp: datetime | None = None,
    ) -> dict | None:
        """
        Encode and upload a camera frame to S3.

        Args:
            frame: BGR image (numpy array).
            jpeg_quality: JPEG compression quality (1-100).
            timestamp: Optional timestamp; defaults to now (UTC).

        Returns:
            dict with upload details on success, None on failure.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Step 1: Encode to JPEG
        jpeg_bytes = self._encode_jpeg(frame, jpeg_quality)
        if jpeg_bytes is None:
            return None

        logger.info(
            "Uploading image: size=%d bytes, timestamp=%s",
            len(jpeg_bytes),
            timestamp.isoformat(),
        )

        # Step 2: Request pre-signed URL
        presigned_data = self._request_presigned_url(timestamp)
        if presigned_data is None:
            return None

        # Step 3: Upload to S3
        success = self._upload_to_s3(presigned_data["upload_url"], jpeg_bytes)
        if not success:
            return None

        self._upload_count += 1
        result = {
            "device_id": self.device_config.device_id,
            "timestamp": timestamp.isoformat(),
            "s3_key": presigned_data.get("s3_key", ""),
            "size_bytes": len(jpeg_bytes),
            "upload_number": self._upload_count,
        }
        logger.info("Upload #%d successful: %s", self._upload_count, result["s3_key"])
        return result

    def _encode_jpeg(self, frame: np.ndarray, quality: int) -> bytes | None:
        """Encode frame to JPEG bytes."""
        try:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            success, buffer = cv2.imencode(".jpg", frame, encode_params)
            if not success:
                logger.error("Failed to encode frame to JPEG")
                return None
            return buffer.tobytes()
        except Exception as e:
            logger.error("JPEG encoding error: %s", e)
            return None

    def _request_presigned_url(self, timestamp: datetime) -> dict | None:
        """
        Request a pre-signed URL from the API Gateway.

        Returns:
            dict with 'upload_url' and 's3_key' on success, None on failure.
        """
        url = (
            f"{self.upload_config.api_endpoint}"
            f"{self.upload_config.presigned_url_path}"
        )
        payload = {
            "deviceId": self.device_config.device_id,
            "timestamp": timestamp.isoformat(),
        }

        for attempt in range(1, self.upload_config.max_retries + 1):
            try:
                response = self._session.post(
                    url, json=payload, timeout=self.upload_config.timeout
                )
                response.raise_for_status()
                data = response.json()

                if "upload_url" not in data:
                    logger.error("Response missing 'upload_url': %s", data)
                    return None

                logger.debug("Pre-signed URL obtained (attempt %d)", attempt)
                return data

            except requests.exceptions.HTTPError as e:
                logger.warning(
                    "HTTP error requesting presigned URL (attempt %d/%d): %s",
                    attempt,
                    self.upload_config.max_retries,
                    e,
                )
            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    "Connection error (attempt %d/%d): %s",
                    attempt,
                    self.upload_config.max_retries,
                    e,
                )
            except requests.exceptions.Timeout:
                logger.warning(
                    "Timeout requesting presigned URL (attempt %d/%d)",
                    attempt,
                    self.upload_config.max_retries,
                )
            except Exception as e:
                logger.error("Unexpected error requesting presigned URL: %s", e)
                return None

            if attempt < self.upload_config.max_retries:
                delay = self.upload_config.retry_delay * attempt
                logger.info("Retrying in %.1f seconds...", delay)
                time.sleep(delay)

        self._error_count += 1
        logger.error("Failed to obtain presigned URL after %d attempts", self.upload_config.max_retries)
        return None

    def _upload_to_s3(self, presigned_url: str, jpeg_bytes: bytes) -> bool:
        """
        Upload JPEG bytes to S3 using the pre-signed URL (HTTPS PUT).
        """
        for attempt in range(1, self.upload_config.max_retries + 1):
            try:
                response = requests.put(
                    presigned_url,
                    data=jpeg_bytes,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=self.upload_config.upload_timeout,
                )
                response.raise_for_status()
                logger.debug("S3 upload successful (attempt %d)", attempt)
                return True

            except requests.exceptions.HTTPError as e:
                logger.warning(
                    "S3 upload HTTP error (attempt %d/%d): %s",
                    attempt,
                    self.upload_config.max_retries,
                    e,
                )
            except requests.exceptions.Timeout:
                logger.warning(
                    "S3 upload timeout (attempt %d/%d)",
                    attempt,
                    self.upload_config.max_retries,
                )
            except Exception as e:
                logger.error("S3 upload error: %s", e)
                return False

            if attempt < self.upload_config.max_retries:
                delay = self.upload_config.retry_delay * attempt
                time.sleep(delay)

        self._error_count += 1
        logger.error("S3 upload failed after %d attempts", self.upload_config.max_retries)
        return False

    def send_heartbeat(
        self,
        status: str = "online",
        capture_interval_sec: float | None = None,
        camera_device: str | None = None,
        camera_model: str | None = None,
        camera_source: str | None = None,
        last_capture_at: datetime | None = None,
        last_error: str | None = None,
    ) -> bool:
        """Send a heartbeat to the device health endpoint."""
        url = (
            f"{self.upload_config.api_endpoint}"
            f"{self.device_config.health_endpoint}"
        )
        payload = {
            "deviceId": self.device_config.device_id,
            "status": status,
            "captureIntervalSec": capture_interval_sec,
            "cameraDevice": camera_device,
            "cameraModel": camera_model,
            "cameraSource": camera_source,
            "lastCaptureAt": last_capture_at.isoformat() if last_capture_at else None,
            "lastError": last_error,
            "stats": {
                "uploads": self._upload_count,
                "errors": self._error_count,
            },
        }
        payload = {key: value for key, value in payload.items() if value is not None}

        try:
            response = self._session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug("Heartbeat sent successfully")
            return True
        except Exception as e:
            logger.warning("Heartbeat failed: %s", e)
            return False

    @property
    def stats(self) -> dict:
        """Return upload statistics."""
        return {
            "total_uploads": self._upload_count,
            "total_errors": self._error_count,
        }
