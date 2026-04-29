"""
Motion Detection Module
Uses OpenCV MOG2 background subtraction to detect motion in camera frames.
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

from config import MotionConfig

logger = logging.getLogger("home-security.motion")


@dataclass
class MotionResult:
    """Result of motion detection on a single frame."""
    detected: bool
    contours: list
    bounding_boxes: list[tuple[int, int, int, int]]
    total_area: int
    frame_debug: Optional[np.ndarray] = None


class MotionDetector:
    """
    Detects motion using MOG2 background subtraction.
    
    Flow:
        1. Convert frame to grayscale
        2. Apply Gaussian blur to reduce noise
        3. Apply background subtraction
        4. Threshold + dilate to fill gaps
        5. Find contours and filter by minimum area
    """

    def __init__(self, config: MotionConfig):
        self.config = config
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.history,
            varThreshold=config.var_threshold,
            detectShadows=config.detect_shadows,
        )
        self._warmup_frames = 0
        self._warmup_required = 30  # frames needed for background model

        logger.info(
            "MotionDetector initialized (min_area=%d, threshold=%d)",
            config.min_area,
            config.threshold,
        )

    def detect(self, frame: np.ndarray, debug: bool = False) -> MotionResult:
        """
        Detect motion in the given frame.

        Args:
            frame: BGR image from camera (numpy array).
            debug: If True, include annotated debug frame in result.

        Returns:
            MotionResult with detection state and details.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.config.blur_kernel, 0)

        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(
            gray, learningRate=self.config.learning_rate
        )

        # Warmup phase: background model needs time to stabilize
        self._warmup_frames += 1
        if self._warmup_frames < self._warmup_required:
            logger.debug(
                "Warmup frame %d/%d", self._warmup_frames, self._warmup_required
            )
            return MotionResult(
                detected=False, contours=[], bounding_boxes=[], total_area=0
            )

        # Threshold to binary
        _, thresh = cv2.threshold(
            fg_mask, self.config.threshold, 255, cv2.THRESH_BINARY
        )

        # Dilate to fill gaps
        thresh = cv2.dilate(
            thresh, None, iterations=self.config.dilate_iterations
        )

        # Find contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter by minimum area
        bounding_boxes = []
        total_area = 0
        significant_contours = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.config.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                bounding_boxes.append((x, y, w, h))
                total_area += area
                significant_contours.append(contour)

        detected = len(bounding_boxes) > 0

        # Debug frame with annotations
        debug_frame = None
        if debug and detected:
            debug_frame = frame.copy()
            for x, y, w, h in bounding_boxes:
                cv2.rectangle(debug_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                debug_frame,
                f"Motion: {len(bounding_boxes)} region(s)",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

        if detected:
            logger.debug(
                "Motion detected: %d region(s), total_area=%d",
                len(bounding_boxes),
                total_area,
            )

        return MotionResult(
            detected=detected,
            contours=significant_contours,
            bounding_boxes=bounding_boxes,
            total_area=total_area,
            frame_debug=debug_frame,
        )

    def reset(self):
        """Reset the background model."""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.config.history,
            varThreshold=self.config.var_threshold,
            detectShadows=self.config.detect_shadows,
        )
        self._warmup_frames = 0
        logger.info("Background model reset")
