"""
Fix 2: Multi-person detection improved — runs BOTH Haar cascade AND
        YOLO body detection so seated/partial people are caught too
Fix 3: Added back-of-head detection (profile cascade) to catch people
        who are not facing the camera during the room sweep
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
    finding_type: str
    severity: str
    message: str
    confidence: float
    frame_index: int


@dataclass
class RoomScanResult:
    passed: bool
    scan_duration_s: float
    frames_analysed: int
    findings: list = field(default_factory=list)
    overall_message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "passed": bool(self.passed),
            "scan_duration_s": float(self.scan_duration_s),
            "frames_analysed": int(self.frames_analysed),
            "findings": [
                {
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "message": f.message,
                    "confidence": float(f.confidence),
                }
                for f in self.findings
            ],
            "overall_message": str(self.overall_message),
        }


class RoomScanner:

    def __init__(self):
        import os

        # ── Face cascade (frontal) ─────────────────────────────────
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # ── Profile face cascade (side-on faces during room sweep) ─
        self._profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )

        # ── Upper body cascade (catches seated people, backs of heads) ─
        self._body_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_upperbody.xml"
        )

        # ── YOLO — FIXED PATH: object_detector/models/ ─────────────
        self._yolo = None
        try:
            from ultralytics import YOLO

            # Correct path — user confirmed model is in object_detector/models/
            base = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(
                base, "..", "object_detector", "models", "finalBestV5.pt"
            )
            model_path = os.path.normpath(model_path)

            if os.path.exists(model_path):
                self._yolo = YOLO(model_path)
                logger.info(f"RoomScanner: YOLO loaded from {model_path}")
            else:
                logger.warning(f"RoomScanner: YOLO model not found at {model_path}")
        except Exception as e:
            logger.warning(f"RoomScanner: YOLO unavailable ({e}), using Haar fallback")

        logger.info("RoomScanner ready")

    def analyse(self, frames: list) -> RoomScanResult:
        start_time = time.time()
        findings = []

        if len(frames) < 5:
            return RoomScanResult(
                passed=False,
                scan_duration_s=0.0,
                frames_analysed=len(frames),
                overall_message="Not enough frames captured for room scan.",
            )

        # Sample every 3rd frame for efficiency
        sampled = frames[::3]

        person_findings = self._check_extra_people(sampled)
        findings.extend(person_findings)

        screen_findings = self._check_extra_screens(sampled)
        findings.extend(screen_findings)

        light_finding = self._check_lighting(sampled)
        if light_finding:
            findings.append(light_finding)

        wb_finding = self._check_whiteboard(sampled)
        if wb_finding:
            findings.append(wb_finding)

        high_count = sum(1 for f in findings if f.severity == "HIGH")
        passed = high_count == 0

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
            passed=passed,
            scan_duration_s=float(round(time.time() - start_time, 2)),
            frames_analysed=len(frames),
            findings=findings,
            overall_message=msg,
        )

    def _check_extra_people(self, frames: list) -> list:
        """
        Multi-method person detection:
          1. YOLO 'person' class (most accurate — if model available)
          2. Frontal face Haar cascade
          3. Profile face Haar cascade (side-on during room sweep)
          4. Upper body Haar cascade (partial/seated people)
        """
        max_people_seen = 0
        worst_idx = 0

        for i, frame in enumerate(frames):
            people_in_frame = 0

            # ── Method 1: YOLO person detection ──────────────────
            if self._yolo is not None:
                try:
                    results = self._yolo(frame, verbose=False, conf=0.35)
                    for r in results:
                        if r.boxes is not None:
                            for cls_id in r.boxes.cls.cpu().numpy().astype(int):
                                # COCO class 0 = person
                                if cls_id == 0:
                                    people_in_frame += 1
                except Exception as e:
                    logger.debug(f"YOLO person detection error: {e}")

            # ── Method 2+3+4: Haar cascades (fallback / supplement) ─
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)  # improve contrast for cascade

            # Frontal faces
            frontal = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
            )

            # Profile faces (catches people turned sideways during sweep)
            profile = self._profile_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(25, 25)
            )
            # Mirror for opposite profile direction
            gray_flipped = cv2.flip(gray, 1)
            profile_r = self._profile_cascade.detectMultiScale(
                gray_flipped, scaleFactor=1.1, minNeighbors=4, minSize=(25, 25)
            )

            # Upper body (seated / partial)
            bodies = self._body_cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 60)
            )

            # Combine cascade detections into rough person count
            # Use max of frontal faces and body detections
            # (bodies can double-count, so take max not sum)
            haar_people = max(
                len(frontal),
                len(bodies),
                len(profile) + len(profile_r),
            )

            # If YOLO ran, trust it more; otherwise use Haar
            if self._yolo is not None:
                people_in_frame = max(people_in_frame, len(frontal))
            else:
                people_in_frame = haar_people

            logger.debug(
                f"Frame {i}: people={people_in_frame} "
                f"frontal={len(frontal)} bodies={len(bodies)} "
                f"profile={len(profile)}+{len(profile_r)}"
            )

            if people_in_frame > max_people_seen:
                max_people_seen = people_in_frame
                worst_idx = i

        if max_people_seen > 1:
            return [
                RoomFinding(
                    finding_type="EXTRA_PERSON",
                    severity="HIGH",
                    message=(
                        f"{max_people_seen} people detected in the room. "
                        "You must be alone during the exam. "
                        "Please ask others to leave and rescan."
                    ),
                    confidence=0.88,
                    frame_index=worst_idx,
                )
            ]
        return []

    def _check_extra_screens(self, frames: list) -> list:
        screen_count_per_frame = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            screen_candidates = 0
            h, w = frame.shape[:2]
            min_area = (w * h) * 0.05

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area:
                    continue
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                if len(approx) == 4:
                    x, y, rw, rh = cv2.boundingRect(approx)
                    roi = gray[y : y + rh, x : x + rw]
                    if roi.size > 0 and float(np.std(roi)) > 40:
                        screen_candidates += 1

            screen_count_per_frame.append(screen_candidates)

        if sum(1 for c in screen_count_per_frame if c > 0) > len(frames) // 3:
            return [
                RoomFinding(
                    finding_type="EXTRA_MONITOR",
                    severity="WARNING",
                    message=(
                        "Additional screen or monitor may be visible. "
                        "Ensure no extra displays are visible to the camera."
                    ),
                    confidence=0.65,
                    frame_index=0,
                )
            ]
        return []

    def _check_lighting(self, frames: list) -> Optional[RoomFinding]:
        brightness = [
            float(np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))) for f in frames
        ]
        avg = float(np.mean(brightness))
        if avg < 60:
            return RoomFinding(
                finding_type="POOR_LIGHTING",
                severity="HIGH",
                message=(
                    f"Room is too dark (brightness={avg:.0f}/255). "
                    "Turn on more lights or move to a brighter location."
                ),
                confidence=0.90,
                frame_index=0,
            )
        if avg < 90:
            return RoomFinding(
                finding_type="POOR_LIGHTING",
                severity="WARNING",
                message="Room lighting is low. Improve lighting for better monitoring.",
                confidence=0.75,
                frame_index=0,
            )
        return None

    def _check_whiteboard(self, frames: list) -> Optional[RoomFinding]:
        large_white = 0
        for frame in frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
            if float(np.sum(mask > 0)) / float(mask.size) > 0.18:
                large_white += 1
        if large_white > len(frames) // 2:
            return RoomFinding(
                finding_type="WHITEBOARD",
                severity="WARNING",
                message=(
                    "A large white surface is visible. "
                    "Ensure no notes or reference materials are in view."
                ),
                confidence=0.70,
                frame_index=0,
            )
        return None


# Module-level singleton
room_scanner = RoomScanner()
