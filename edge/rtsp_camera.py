"""
RTSP camera wrapper for Imou Ranger WiFi cameras.
"""

import logging
import os
import time

import cv2
import numpy as np

from config import CameraConfig

logger = logging.getLogger("home-security.rtsp")


class RTSPCameraWrapper:
    """Capture frames from an RTSP stream with reconnect and frame validation."""

    def __init__(self, config: CameraConfig):
        self.config = config
        self.rtsp_url = config.rtsp_url
        self._cap: cv2.VideoCapture | None = None
        self._last_reconnect_at = 0.0
        self._next_reconnect_at = 0.0
        self._reconnect_count = 0
        self.last_error: str | None = None

        if not self.rtsp_url:
            raise ValueError("RTSP_URL is required when CAMERA_SOURCE_TYPE=rtsp")

        self._connect()

    @property
    def health_status(self) -> str:
        if self.last_error:
            return "degraded"
        return "online"

    @property
    def source_description(self) -> str:
        return "rtsp"

    def _connect(self):
        options = [
            f"rtsp_transport;{self.config.rtsp_transport}",
            f"stimeout;{self.config.rtsp_timeout * 1_000_000}",
        ]
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(options)

        if self._cap:
            self._cap.release()

        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
        self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        if self._cap.isOpened():
            self.last_error = None
            self._reconnect_count = 0
            self._next_reconnect_at = 0.0
            logger.info("Connected to RTSP camera (%s)", self.config.camera_model)
        else:
            self.last_error = "RTSP stream could not be opened"
            logger.warning(self.last_error)

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._cap or not self._cap.isOpened():
            if not self._reconnect_due():
                return False, None
            self._connect()

        if not self._cap:
            return False, None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self.last_error = "RTSP frame read failed"
            self._schedule_reconnect()
            return False, None

        if not self._is_valid_frame(frame):
            self.last_error = "RTSP frame failed validation"
            return False, None

        self.last_error = None
        return True, frame

    def _reconnect_due(self) -> bool:
        return time.time() >= self._next_reconnect_at

    def _schedule_reconnect(self):
        now = time.time()
        delay = min(
            self.config.rtsp_reconnect_delay * max(1, self._reconnect_count),
            30,
        )
        self._last_reconnect_at = now
        self._next_reconnect_at = now + delay
        self._reconnect_count += 1
        logger.warning(
            "RTSP reconnect scheduled in %.1fs (attempt %d)",
            delay,
            self._reconnect_count,
        )
        if self._cap:
            self._cap.release()
            self._cap = None

    @staticmethod
    def _is_valid_frame(frame: np.ndarray) -> bool:
        if frame.size == 0:
            return False
        if frame.ndim != 3 or frame.shape[0] < 10 or frame.shape[1] < 10:
            return False
        return float(frame.std()) > 2.0

    def release(self):
        if self._cap:
            self._cap.release()
            self._cap = None
