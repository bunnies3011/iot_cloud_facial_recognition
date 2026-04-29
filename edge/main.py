"""
Home Security Edge Device – Main Application
Raspberry Pi camera capture loop: Motion → Face Detection → Upload.

Usage:
    python main.py
    
Environment Variables:
    DEVICE_ID          - Unique device identifier (default: cam-01)
    API_ENDPOINT       - Cloud API base URL
    API_KEY            - API Gateway key
    CAMERA_WIDTH       - Capture width (default: 640)
    CAMERA_HEIGHT      - Capture height (default: 480)
    LOG_LEVEL          - Logging level (default: INFO)
"""

import os
import sys
import time
import signal
import threading
import logging
from datetime import datetime, timezone

import cv2
import numpy as np

from config import AppConfig, setup_logging
from motion_detector import MotionDetector
from face_detector import FaceDetector
from uploader import ImageUploader
from rtsp_camera import RTSPCameraWrapper

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
_running = True
logger: logging.Logger = None  # type: ignore


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _running
    logger.info("Shutdown signal received (%s). Stopping...", signal.Signals(signum).name)
    _running = False


def heartbeat_loop(
    uploader: ImageUploader,
    interval: int,
    config: AppConfig,
    camera,
    state: dict,
):
    """Background thread that sends periodic heartbeats."""
    while _running:
        camera_status = getattr(camera, "health_status", "online")
        last_error = state.get("last_error") or getattr(camera, "last_error", None)
        status = "degraded" if last_error or camera_status != "online" else "online"
        uploader.send_heartbeat(
            status=status,
            capture_interval_sec=config.capture_cooldown,
            camera_device=getattr(camera, "source_description", config.camera.source_type),
            camera_model=config.camera.camera_model,
            camera_source=config.camera.source_type,
            last_capture_at=state.get("last_capture_at"),
            last_error=last_error,
        )
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)


def init_camera(config: AppConfig):
    """
    Initialize camera capture.
    Supports RTSP, Picamera2, and USB/OpenCV sources.
    """
    if config.camera.source_type == "rtsp":
        logger.info("Initializing RTSP camera source")
        return RTSPCameraWrapper(config.camera)

    if config.camera.source_type == "picamera":
        return _init_picamera(config)

    return _init_usb_camera(config)


def _init_picamera(config: AppConfig):
    """Initialize a directly attached Raspberry Pi camera."""
    try:
        from picamera2 import Picamera2

        picam = Picamera2()
        cam_config = picam.create_still_configuration(
            main={"size": config.camera.resolution, "format": "RGB888"}
        )
        picam.configure(cam_config)
        picam.start()
        logger.info("Picamera2 initialized at %s", config.camera.resolution)

        class PiCameraWrapper:
            """Wrapper to provide a consistent interface."""
            def __init__(self, cam):
                self._cam = cam

            def read(self):
                frame = self._cam.capture_array()
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame_bgr

            def release(self):
                self._cam.stop()
                self._cam.close()

        wrapper = PiCameraWrapper(picam)
        wrapper.health_status = "online"
        wrapper.source_description = "picamera"
        return wrapper

    except (ImportError, RuntimeError) as e:
        logger.error("Picamera2 not available: %s", e)
        sys.exit(1)


def _init_usb_camera(config: AppConfig):
    """Initialize an OpenCV USB camera."""
    cap = cv2.VideoCapture(config.camera.device_index)
    if not cap.isOpened():
        logger.error("Cannot open camera (VideoCapture index %d)", config.camera.device_index)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.resolution[1])
    cap.set(cv2.CAP_PROP_FPS, config.camera.fps)

    logger.info(
        "OpenCV VideoCapture initialized at %dx%d @ %d fps",
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        int(cap.get(cv2.CAP_PROP_FPS)),
    )
    class OpenCVCameraWrapper:
        """Wrapper to provide heartbeat metadata for OpenCV cameras."""
        health_status = "online"
        source_description = "usb"
        last_error = None

        def __init__(self, capture):
            self._cap = capture

        def read(self):
            ret, frame = self._cap.read()
            self.last_error = None if ret else "USB camera frame read failed"
            return ret, frame

        def release(self):
            self._cap.release()

    return OpenCVCameraWrapper(cap)


def save_local_copy(frame: np.ndarray, save_dir: str, device_id: str):
    """Save a local copy of the captured frame (for debugging)."""
    os.makedirs(save_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{device_id}_{ts}.jpg"
    path = os.path.join(save_dir, filename)
    cv2.imwrite(path, frame)
    logger.debug("Local copy saved: %s", path)


def main():
    global logger

    # ---- Configuration ----
    config = AppConfig.from_env()
    logger = setup_logging(config.log_level)

    logger.info("=" * 60)
    logger.info("Home Security Edge Device Starting")
    logger.info("Device ID  : %s", config.device.device_id)
    logger.info("Resolution : %s", config.camera.resolution)
    logger.info("Camera     : %s (%s)", config.camera.camera_model, config.camera.source_type)
    logger.info("Face Model : %s", config.face_detection.model_type)
    logger.info("API        : %s", config.upload.api_endpoint or "(not set)")
    logger.info("=" * 60)

    # ---- Validate ----
    if not config.upload.api_endpoint:
        logger.warning(
            "API_ENDPOINT not set. Images will NOT be uploaded. "
            "Set API_ENDPOINT env var to enable cloud upload."
        )

    # ---- Initialize components ----
    motion_detector = MotionDetector(config.motion)
    face_detector = FaceDetector(config.face_detection)

    uploader = None
    if config.upload.api_endpoint:
        uploader = ImageUploader(config.upload, config.device)

    camera = init_camera(config)
    runtime_state = {"last_capture_at": None, "last_error": None}

    # ---- Signal handlers ----
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ---- Heartbeat thread ----
    if uploader:
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            args=(uploader, config.device.heartbeat_interval, config, camera, runtime_state),
            daemon=True,
        )
        heartbeat_thread.start()
        logger.info(
            "Heartbeat thread started (interval=%ds)",
            config.device.heartbeat_interval,
        )

    # ---- Main loop ----
    last_capture_time = 0.0
    frame_count = 0
    detection_count = 0

    logger.info("Starting capture loop. Press Ctrl+C to stop.")

    try:
        while _running:
            ret, frame = camera.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                runtime_state["last_error"] = getattr(
                    camera, "last_error", "camera frame read failed"
                )
                time.sleep(0.1)
                continue
            runtime_state["last_error"] = None

            frame_count += 1

            # Step 1: Motion detection
            motion_result = motion_detector.detect(frame)
            if not motion_result.detected:
                time.sleep(1.0 / config.camera.fps)
                continue

            # Cooldown check
            now = time.time()
            if now - last_capture_time < config.capture_cooldown:
                continue

            # Step 2: Face detection (edge filtering)
            face_result = face_detector.detect(frame)
            if not face_result.detected:
                logger.debug("Motion detected but no face found — skipping upload")
                continue

            # ---- Face detected! ----
            detection_count += 1
            last_capture_time = now
            timestamp = datetime.now(timezone.utc)
            runtime_state["last_capture_at"] = timestamp

            logger.info(
                "🔔 Detection #%d: %d face(s) found at %s",
                detection_count,
                face_result.face_count,
                timestamp.isoformat(),
            )

            # Save local copy (optional)
            if config.save_local_copy:
                save_local_copy(
                    frame, config.local_save_dir, config.device.device_id
                )

            # Step 3: Upload to cloud
            if uploader:
                result = uploader.upload_frame(
                    frame,
                    jpeg_quality=config.camera.jpeg_quality,
                    timestamp=timestamp,
                )
                if result:
                    logger.info("✅ Uploaded: %s", result["s3_key"])
                else:
                    logger.error("❌ Upload failed for detection #%d", detection_count)

    except Exception as e:
        logger.exception("Unexpected error in main loop: %s", e)
    finally:
        logger.info("Shutting down...")
        camera.release()
        logger.info(
            "Session summary: %d frames processed, %d detections, uploads=%s",
            frame_count,
            detection_count,
            uploader.stats if uploader else "N/A",
        )
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
