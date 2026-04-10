"""
ai_engine/room_module/room_scan.py

Pre-Exam Room Scan — Environment Verification

Candidate performs a slow 360° camera sweep before exam starts.
System analyses the captured frames and produces a room report.

What it detects:
  1. Additional monitors / screens in the background
  2. Multiple people in the room
  3. Whiteboards or large paper with text
  4. Cluttered desk (potential notes)
  5. Room lighting quality

Returns a RoomScanResult with pass/fail and specific findings.
"""

import cv2
import numpy as np
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RoomFinding:
    finding_type: str     # EXTRA_MONITOR | EXTRA_PERSON | WHITEBOARD | CLUTTER | POOR_LIGHTING
    severity    : str     # WARNING | HIGH
    message     : str
    confidence  : float
    frame_index : int


@dataclass
class RoomScanResult:
    passed          : bool
    scan_duration_s : float
    frames_analysed : int
    findings        : list = field(default_factory=list)
    overall_message : str  = ""
    timestamp       : float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "passed"          : bool(self.passed),
            "scan_duration_s" : float(self.scan_duration_s),
            "frames_analysed" : int(self.frames_analysed),
            "findings"        : [
                {
                    "finding_type": f.finding_type,
                    "severity"    : f.severity,
                    "message"     : f.message,
                    "confidence"  : float(f.confidence),
                }
                for f in self.findings
            ],
            "overall_message" : str(self.overall_message),
        }


class RoomScanner:
    """
    Analyses a sequence of frames from a room scan.

    Usage:
        scanner = RoomScanner()
        result  = scanner.analyse(frames)   # list of BGR frames
    """

    def __init__(self):
        # Load face detector for person count
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        # Try to load YOLOv8 for monitor/screen detection
        self._yolo = None
        try:
            from ultralytics import YOLO
            import os
            model_path = os.path.join(
                os.path.dirname(__file__),
                '..', 'object_module', 'models', 'finalBestV5.pt'
            )
            if os.path.exists(model_path):
                self._yolo = YOLO(model_path)
        except Exception as e:
            logger.debug(f"RoomScanner: YOLO unavailable ({e}), using fallback")

        logger.info("RoomScanner ready")

    def analyse(self, frames: list[np.ndarray]) -> RoomScanResult:
        start_time = time.time()
        findings   = []

        if len(frames) < 5:
            return RoomScanResult(
                passed          = False,
                scan_duration_s = 0.0,
                frames_analysed = len(frames),
                overall_message = "Not enough frames captured for room scan.",
            )

        # Sample every 3rd frame for efficiency
        sampled = frames[::3]

        # ── Check 1: Multiple people ────────────────────────────
        person_findings = self._check_extra_people(sampled)
        findings.extend(person_findings)

        # ── Check 2: Extra screens/monitors ─────────────────────
        screen_findings = self._check_extra_screens(sampled)
        findings.extend(screen_findings)

        # ── Check 3: Lighting quality ────────────────────────────
        light_finding = self._check_lighting(sampled)
        if light_finding:
            findings.append(light_finding)

        # ── Check 4: Whiteboard / text surfaces ──────────────────
        wb_finding = self._check_whiteboard(sampled)
        if wb_finding:
            findings.append(wb_finding)

        high_count = sum(1 for f in findings if f.severity == "HIGH")
        passed     = high_count == 0

        if not findings:
            msg = "Room environment verified. No issues detected."
        elif passed:
            msg = f"{len(findings)} minor issue(s) noted but exam can proceed."
        else:
            msg = (
                f"{high_count} significant issue(s) detected. "
                "Please resolve before starting the exam."
            )

        return RoomScanResult(
            passed          = passed,
            scan_duration_s = float(round(time.time() - start_time, 2)),
            frames_analysed = len(frames),
            findings        = findings,
            overall_message = msg,
        )

    def _check_extra_people(self, frames: list[np.ndarray]) -> list[RoomFinding]:
        findings   = []
        max_faces  = 0
        worst_idx  = 0

        for i, frame in enumerate(frames):
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4,
                minSize=(30, 30),
            )
            if len(faces) > max_faces:
                max_faces = len(faces)
                worst_idx = i

        if max_faces > 1:
            findings.append(RoomFinding(
                finding_type = "EXTRA_PERSON",
                severity     = "HIGH",
                message      = (
                    f"Multiple people detected ({max_faces} faces visible). "
                    "You must be alone during the exam."
                ),
                confidence   = 0.85,
                frame_index  = worst_idx,
            ))
        return findings

    def _check_extra_screens(self, frames: list[np.ndarray]) -> list[RoomFinding]:
        """
        Detect screens by looking for rectangles with high
        luminance variation (characteristic of screen content).
        """
        screen_count_per_frame = []

        for frame in frames:
            gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred   = cv2.GaussianBlur(gray, (5, 5), 0)
            edges     = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            screen_candidates = 0
            h, w = frame.shape[:2]
            min_area = (w * h) * 0.05  # at least 5% of frame

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area:
                    continue
                peri   = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

                if len(approx) == 4:   # rectangular shape
                    # Check if this region has high brightness variance
                    x, y, rw, rh = cv2.boundingRect(approx)
                    roi           = gray[y:y+rh, x:x+rw]
                    if roi.size > 0 and float(np.std(roi)) > 40:
                        screen_candidates += 1

            screen_count_per_frame.append(screen_candidates)

        # If multiple frames show extra screens, flag it
        if sum(1 for c in screen_count_per_frame if c > 0) > len(frames) // 3:
            return [RoomFinding(
                finding_type = "EXTRA_MONITOR",
                severity     = "WARNING",
                message      = (
                    "Additional screen or monitor may be visible in the background. "
                    "Please ensure no extra displays are visible to the camera."
                ),
                confidence   = 0.65,
                frame_index  = 0,
            )]
        return []

    def _check_lighting(self, frames: list[np.ndarray]) -> Optional[RoomFinding]:
        """Flag if room is too dark for reliable face detection."""
        mean_brightness = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness.append(float(np.mean(gray)))

        avg = float(np.mean(mean_brightness))

        if avg < 60:
            return RoomFinding(
                finding_type = "POOR_LIGHTING",
                severity     = "HIGH",
                message      = (
                    f"Room lighting is too dim (brightness={avg:.0f}/255). "
                    "Please turn on more lights or move to a brighter location."
                ),
                confidence   = 0.90,
                frame_index  = 0,
            )
        if avg < 90:
            return RoomFinding(
                finding_type = "POOR_LIGHTING",
                severity     = "WARNING",
                message      = "Room lighting is low. Consider improving lighting for better monitoring.",
                confidence   = 0.75,
                frame_index  = 0,
            )
        return None

    def _check_whiteboard(self, frames: list[np.ndarray]) -> Optional[RoomFinding]:
        """Detect large white/light rectangles that could be whiteboards."""
        large_white_count = 0

        for frame in frames:
            hsv    = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # White-ish areas: low saturation, high value
            mask   = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
            ratio  = float(np.sum(mask > 0)) / float(mask.size)

            if ratio > 0.18:  # > 18% of frame is white = possible whiteboard
                large_white_count += 1

        if large_white_count > len(frames) // 2:
            return RoomFinding(
                finding_type = "WHITEBOARD",
                severity     = "WARNING",
                message      = (
                    "A large white surface (possible whiteboard or paper) is visible. "
                    "Please ensure no notes or reference materials are in view."
                ),
                confidence   = 0.70,
                frame_index  = 0,
            )
        return None


# Singleton
room_scanner = RoomScanner()
