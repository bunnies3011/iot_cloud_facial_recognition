"""
Edge Device Configuration
Raspberry Pi camera security system settings.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CameraConfig:
    """Camera capture settings."""
    source_type: str = "rtsp"  # "rtsp", "picamera", or "usb"
    resolution: tuple[int, int] = (640, 480)
    fps: int = 15
    rotation: int = 0
    format: str = "rgb"
    jpeg_quality: int = 85
    device_index: int = 0
    rtsp_url: str = ""
    rtsp_transport: str = "tcp"
    rtsp_timeout: int = 10
    rtsp_reconnect_delay: int = 5
    camera_model: str = "Imou Ranger"


@dataclass
class MotionConfig:
    """Motion detection settings."""
    min_area: int = 5000
    blur_kernel: tuple[int, int] = (21, 21)
    threshold: int = 25
    dilate_iterations: int = 2
    history: int = 500
    var_threshold: float = 16.0
    detect_shadows: bool = True
    learning_rate: float = -1.0  # auto


@dataclass
class FaceDetectionConfig:
    """Face detection (edge) settings."""
    model_type: str = "haar"  # "haar" or "dnn"
    confidence_threshold: float = 0.5
    # Haar cascade
    scale_factor: float = 1.1
    min_neighbors: int = 5
    min_face_size: tuple[int, int] = (30, 30)
    # DNN (MobileNet SSD)
    prototxt_path: str = "models/deploy.prototxt"
    model_path: str = "models/res10_300x300_ssd_iter_140000.caffemodel"


@dataclass
class UploadConfig:
    """Upload / API settings."""
    api_endpoint: str = ""
    api_key: str = ""
    presigned_url_path: str = "/api/presigned-url"
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    upload_timeout: int = 60


@dataclass
class DeviceConfig:
    """Device identity and heartbeat."""
    device_id: str = "cam-01"
    heartbeat_interval: int = 60  # seconds
    health_endpoint: str = "/api/devices/heartbeat"


@dataclass
class AppConfig:
    """Root application configuration."""
    camera: CameraConfig = field(default_factory=CameraConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    face_detection: FaceDetectionConfig = field(default_factory=FaceDetectionConfig)
    upload: UploadConfig = field(default_factory=UploadConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)

    # General
    capture_cooldown: float = 2.0  # min seconds between captures
    log_level: str = "INFO"
    save_local_copy: bool = False
    local_save_dir: str = "captures"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        config = cls()

        # Device
        config.device.device_id = os.getenv("DEVICE_ID", config.device.device_id)

        # API
        config.upload.api_endpoint = os.getenv(
            "API_ENDPOINT", config.upload.api_endpoint
        )
        config.upload.api_key = os.getenv("API_KEY", config.upload.api_key)

        # Camera
        config.camera.source_type = os.getenv(
            "CAMERA_SOURCE_TYPE", config.camera.source_type
        ).lower()
        width = int(os.getenv("CAMERA_WIDTH", config.camera.resolution[0]))
        height = int(os.getenv("CAMERA_HEIGHT", config.camera.resolution[1]))
        config.camera.resolution = (width, height)
        config.camera.fps = int(os.getenv("CAMERA_FPS", config.camera.fps))
        config.camera.jpeg_quality = int(
            os.getenv("JPEG_QUALITY", config.camera.jpeg_quality)
        )
        config.camera.device_index = int(
            os.getenv("CAMERA_DEVICE_INDEX", config.camera.device_index)
        )
        config.camera.rtsp_url = os.getenv("RTSP_URL", config.camera.rtsp_url)
        config.camera.rtsp_transport = os.getenv(
            "RTSP_TRANSPORT", config.camera.rtsp_transport
        ).lower()
        config.camera.rtsp_timeout = int(
            os.getenv("RTSP_TIMEOUT", config.camera.rtsp_timeout)
        )
        config.camera.rtsp_reconnect_delay = int(
            os.getenv("RTSP_RECONNECT_DELAY", config.camera.rtsp_reconnect_delay)
        )
        config.camera.camera_model = os.getenv(
            "CAMERA_MODEL", config.camera.camera_model
        )

        # Motion
        config.motion.min_area = int(
            os.getenv("MOTION_MIN_AREA", config.motion.min_area)
        )
        config.motion.threshold = int(
            os.getenv("MOTION_THRESHOLD", config.motion.threshold)
        )

        # Face
        config.face_detection.model_type = os.getenv(
            "FACE_MODEL_TYPE", config.face_detection.model_type
        )
        config.face_detection.confidence_threshold = float(
            os.getenv(
                "FACE_CONFIDENCE_THRESHOLD",
                config.face_detection.confidence_threshold,
            )
        )

        # General
        config.capture_cooldown = float(
            os.getenv("CAPTURE_COOLDOWN", config.capture_cooldown)
        )
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)
        config.save_local_copy = (
            os.getenv("SAVE_LOCAL_COPY", "false").lower() == "true"
        )

        return config


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the application logger."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("home-security")
    logger.setLevel(log_level)
    return logger
