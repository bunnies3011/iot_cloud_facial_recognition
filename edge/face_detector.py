"""
Face Detection Module (Edge)
Lightweight face detection using Haar Cascade or DNN (MobileNet SSD).
Only detects presence of faces — recognition happens in the cloud via Rekognition.
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

from config import FaceDetectionConfig

logger = logging.getLogger("home-security.face")


@dataclass
class FaceDetectionResult:
    """Result of face detection on a single frame."""
    detected: bool
    face_count: int
    bounding_boxes: list[tuple[int, int, int, int]]
    confidences: list[float]
    frame_debug: Optional[np.ndarray] = None


class FaceDetector:
    """
    Detect faces in frames using one of two methods:
    - 'haar': OpenCV Haar Cascade (very fast, less accurate)
    - 'dnn': OpenCV DNN with pre-trained caffe model (slower, more accurate)
    """

    def __init__(self, config: FaceDetectionConfig):
        self.config = config

        if config.model_type == "haar":
            self._init_haar()
        elif config.model_type == "dnn":
            self._init_dnn()
        else:
            raise ValueError(f"Unknown model type: {config.model_type}")

        logger.info(
            "FaceDetector initialized (model=%s, threshold=%.2f)",
            config.model_type,
            config.confidence_threshold,
        )

    def _init_haar(self):
        """Initialize Haar Cascade classifier."""
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.classifier = cv2.CascadeClassifier(cascade_path)
        if self.classifier.empty():
            raise RuntimeError(f"Failed to load Haar cascade from {cascade_path}")
        logger.info("Haar Cascade loaded from: %s", cascade_path)

    def _init_dnn(self):
        """Initialize DNN face detector (Caffe model)."""
        try:
            self.net = cv2.dnn.readNetFromCaffe(
                self.config.prototxt_path,
                self.config.model_path,
            )
            logger.info("DNN model loaded: %s", self.config.model_path)
        except cv2.error as e:
            raise RuntimeError(
                f"Failed to load DNN model. "
                f"Ensure {self.config.prototxt_path} and {self.config.model_path} exist. "
                f"Error: {e}"
            )

    def detect(self, frame: np.ndarray, debug: bool = False) -> FaceDetectionResult:
        """
        Detect faces in the given frame.

        Args:
            frame: BGR image (numpy array).
            debug: If True, include annotated debug frame.

        Returns:
            FaceDetectionResult with detection details.
        """
        if self.config.model_type == "haar":
            return self._detect_haar(frame, debug)
        else:
            return self._detect_dnn(frame, debug)

    def _detect_haar(
        self, frame: np.ndarray, debug: bool = False
    ) -> FaceDetectionResult:
        """Detect faces using Haar Cascade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.classifier.detectMultiScale(
            gray,
            scaleFactor=self.config.scale_factor,
            minNeighbors=self.config.min_neighbors,
            minSize=self.config.min_face_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        bounding_boxes = []
        confidences = []

        for x, y, w, h in faces:
            bounding_boxes.append((int(x), int(y), int(w), int(h)))
            confidences.append(1.0)  # Haar doesn't provide confidence

        detected = len(bounding_boxes) > 0

        debug_frame = None
        if debug and detected:
            debug_frame = self._draw_debug(frame, bounding_boxes, confidences)

        if detected:
            logger.info("Face detected (Haar): %d face(s)", len(bounding_boxes))

        return FaceDetectionResult(
            detected=detected,
            face_count=len(bounding_boxes),
            bounding_boxes=bounding_boxes,
            confidences=confidences,
            frame_debug=debug_frame,
        )

    def _detect_dnn(
        self, frame: np.ndarray, debug: bool = False
    ) -> FaceDetectionResult:
        """Detect faces using DNN (MobileNet SSD)."""
        h, w = frame.shape[:2]

        # Pre-process: resize to 300x300, mean subtraction
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            scalefactor=1.0,
            size=(300, 300),
            mean=(104.0, 177.0, 123.0),
        )

        self.net.setInput(blob)
        detections = self.net.forward()

        bounding_boxes = []
        confidences = []

        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])

            if confidence >= self.config.confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")

                # Clamp to image boundaries
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                bw = x2 - x1
                bh = y2 - y1
                if bw > 0 and bh > 0:
                    bounding_boxes.append((x1, y1, bw, bh))
                    confidences.append(confidence)

        detected = len(bounding_boxes) > 0

        debug_frame = None
        if debug and detected:
            debug_frame = self._draw_debug(frame, bounding_boxes, confidences)

        if detected:
            logger.info(
                "Face detected (DNN): %d face(s), max_conf=%.2f",
                len(bounding_boxes),
                max(confidences) if confidences else 0,
            )

        return FaceDetectionResult(
            detected=detected,
            face_count=len(bounding_boxes),
            bounding_boxes=bounding_boxes,
            confidences=confidences,
            frame_debug=debug_frame,
        )

    @staticmethod
    def _draw_debug(
        frame: np.ndarray,
        boxes: list[tuple[int, int, int, int]],
        confidences: list[float],
    ) -> np.ndarray:
        """Draw bounding boxes and labels on a copy of the frame."""
        debug_frame = frame.copy()
        for (x, y, w, h), conf in zip(boxes, confidences):
            color = (0, 255, 0)
            cv2.rectangle(debug_frame, (x, y), (x + w, y + h), color, 2)
            label = f"Face {conf:.0%}"
            cv2.putText(
                debug_frame,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )
        return debug_frame
