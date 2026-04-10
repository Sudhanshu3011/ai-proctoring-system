"""
ai_engine/face_module/continuous_liveness.py

Continuous liveness monitor for use DURING an exam session.

Unlike enrollment liveness (which checks a 3-second burst once),
this module runs in the background throughout the exam and
accumulates evidence across a rolling window of frames.

What it detects:
    1. Blink absence — if no blink detected in N seconds, flag it
    2. Head frozen  — if nose position hasn't moved for N seconds
    3. Face absent  — face disappears entirely (already in detector.py)
    4. Static frame — consecutive frames are pixel-identical (photo on screen)

Why multi-frame for continuous liveness:
    A single-frame check would fire constantly for normal exam behaviour
    (student is focused, not blinking every frame).
    The rolling window approach only flags when behaviour is
    abnormal for a sustained period — not just one frame.
"""

import time
import logging
import numpy as np
import cv2
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
class LivenessMonitorConfig:
    # Rolling window size (seconds)
    WINDOW_SECONDS         = 15.0

    # Blink absence — flag if no blink in this many seconds
    BLINK_ABSENCE_THRESHOLD = 15.0    # 15s without blink = suspicious

    # Head freeze — flag if nose moves < N pixels in window
    HEAD_FREEZE_MIN_PX     = 4.0      # pixels of movement required
    HEAD_FREEZE_THRESHOLD  = 12.0     # seconds of no movement = suspicious

    # Static frame — mean pixel diff below this = frames are identical
    STATIC_FRAME_DIFF_THRESHOLD = 0.5  # pixel units
    STATIC_FRAME_MIN_COUNT      = 8    # need N consecutive identical frames

    # Blink detection thresholds
    BLINK_CLOSE_SCORE      = 0.32     # blendshape score = eye closing
    BLINK_OPEN_SCORE       = 0.15     # blendshape score = eye open again


# ─────────────────────────────────────────────
#  Result
# ─────────────────────────────────────────────
@dataclass
class LivenessIssue:
    issue_type : str      # NO_BLINK | HEAD_FROZEN | STATIC_FRAME | FACE_ABSENT
    severity   : str      # WARNING | HIGH
    message    : str      # human-readable message for student display
    confidence : float    # 0.0–1.0
    timestamp  : float    = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "issue_type": self.issue_type,
            "severity"  : self.severity,
            "message"   : self.message,
            "confidence": round(self.confidence, 2),
            "timestamp" : self.timestamp,
        }


# ─────────────────────────────────────────────
#  ContinuousLivenessMonitor
# ─────────────────────────────────────────────
class ContinuousLivenessMonitor:
    """
    Runs throughout an exam session.
    Call update_frame() for each new webcam frame.
    Call get_issues() to retrieve any current liveness flags.

    Usage in video_worker.py or monitoring.py:
        monitor = ContinuousLivenessMonitor()

        # Each frame:
        issues = monitor.update_frame(frame)
        for issue in issues:
            anomaly_detector.add_event(...)
            # send to frontend via WebSocket
    """

    def __init__(self, config: LivenessMonitorConfig = None, model_path: str = None):
        self.config = config or LivenessMonitorConfig()

        # Try to load MediaPipe landmarker
        self._landmarker = None
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                FaceLandmarker, FaceLandmarkerOptions, RunningMode
            )
            import os
            if model_path is None:
                base       = os.path.dirname(os.path.abspath(__file__))
                model_path = os.path.join(base, "models", "face_landmarker.task")

            options = FaceLandmarkerOptions(
                base_options  = BaseOptions(model_asset_path=model_path),
                running_mode  = RunningMode.IMAGE,
                num_faces     = 1,
                min_face_detection_confidence = 0.4,
                min_face_presence_confidence  = 0.4,
                min_tracking_confidence       = 0.4,
                output_face_blendshapes       = True,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
            logger.info("ContinuousLivenessMonitor: landmarker loaded")
        except Exception as e:
            logger.warning(f"ContinuousLivenessMonitor: landmarker unavailable ({e}), using fallback")

        # Rolling data stores
        cfg = self.config
        self._blink_scores : deque = deque()   # (timestamp, max_blink_score)
        self._nose_positions: deque = deque()   # (timestamp, x, y)
        self._frame_grays   : deque = deque()   # (timestamp, gray_array)

        # Blink state machine
        self._blink_state           = "OPEN"   # OPEN | CLOSING
        self._last_blink_time       = time.time()
        self._blink_close_start     = None

        # Issue cooldowns — prevent same issue firing repeatedly
        self._last_issue_time : dict = {}
        self._COOLDOWN_SEC           = 20.0

        self._frame_count = 0

    # ─────────────────────────────────────────
    #  Main entry — call each frame
    # ─────────────────────────────────────────
    def update_frame(self, frame: np.ndarray) -> list[LivenessIssue]:
        """
        Process one webcam frame.
        Returns list of LivenessIssue (empty if all ok).
        """
        self._frame_count += 1
        now = time.time()
        issues = []

        # ── Extract features ───────────────────────────────────────
        if self._landmarker is not None:
            features = self._extract_features(frame, now)
            if features:
                self._blink_scores.append((now, features["blink_max"]))
                self._nose_positions.append((now, features["nose_x"], features["nose_y"]))

                # Update blink state machine
                self._update_blink_state(features["blink_max"], now)

        # Store grayscale for static-frame detection
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (80, 60))
            self._frame_grays.append((now, small))
        except Exception:
            pass

        # ── Prune old data outside rolling window ──────────────────
        cutoff = now - self.config.WINDOW_SECONDS
        self._prune(self._blink_scores,    cutoff)
        self._prune(self._nose_positions,  cutoff)
        self._prune(self._frame_grays,     cutoff)

        # ── Only check every 5th frame to avoid spam ──────────────
        if self._frame_count % 5 != 0:
            return issues

        # ── Run checks ─────────────────────────────────────────────
        if self._landmarker is not None:
            blink_issue = self._check_blink_absence(now)
            if blink_issue:
                issues.append(blink_issue)

            head_issue = self._check_head_frozen(now)
            if head_issue:
                issues.append(head_issue)

        static_issue = self._check_static_frame(now)
        if static_issue:
            issues.append(static_issue)

        return issues

    # ─────────────────────────────────────────
    #  Feature extraction
    # ─────────────────────────────────────────
    def _extract_features(self, frame: np.ndarray, now: float) -> dict | None:
        try:
            import mediapipe as mp
            rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result   = self._landmarker.detect(mp_image)

            if not result.face_landmarks or not result.face_blendshapes:
                return None

            h, w = frame.shape[:2]
            nose = result.face_landmarks[0][1]
            nx   = nose.x * w
            ny   = nose.y * h

            bl = br = 0.0
            for bs in result.face_blendshapes[0]:
                if bs.category_name == "eyeBlinkLeft":
                    bl = bs.score
                elif bs.category_name == "eyeBlinkRight":
                    br = bs.score

            return {
                "nose_x"   : nx,
                "nose_y"   : ny,
                "blink_max": max(bl, br),
            }
        except Exception as e:
            logger.debug(f"Feature extraction error: {e}")
            return None

    # ─────────────────────────────────────────
    #  Blink state machine
    # ─────────────────────────────────────────
    def _update_blink_state(self, blink_score: float, now: float):
        cfg = self.config
        if self._blink_state == "OPEN":
            if blink_score > cfg.BLINK_CLOSE_SCORE:
                self._blink_state       = "CLOSING"
                self._blink_close_start = now
        elif self._blink_state == "CLOSING":
            elapsed = now - (self._blink_close_start or now)
            if elapsed > 0.6:
                # Took too long — reset without counting
                self._blink_state = "OPEN"
            elif blink_score < cfg.BLINK_OPEN_SCORE:
                # Complete blink
                self._last_blink_time = now
                self._blink_state     = "OPEN"
                logger.debug(f"Blink detected at {now:.1f}")

    # ─────────────────────────────────────────
    #  Check 1 — Blink absence
    # ─────────────────────────────────────────
    def _check_blink_absence(self, now: float) -> LivenessIssue | None:
        absence = now - self._last_blink_time
        if absence < self.config.BLINK_ABSENCE_THRESHOLD:
            return None
        if self._is_on_cooldown("NO_BLINK", now):
            return None

        # Scale confidence with how long the absence has been
        max_absence  = self.config.BLINK_ABSENCE_THRESHOLD * 2
        confidence   = min(1.0, (absence - self.config.BLINK_ABSENCE_THRESHOLD) / max_absence)
        secs         = int(absence)

        logger.warning(f"Liveness: no blink detected for {secs}s")
        self._last_issue_time["NO_BLINK"] = now

        return LivenessIssue(
            issue_type = "NO_BLINK",
            severity   = "HIGH" if absence > 100 else "WARNING",
            message    = (
                f"No blink detected for {secs} seconds. "
                "If you are present, please look at the camera and blink naturally."
            ),
            confidence = round(confidence, 2),
        )

    # ─────────────────────────────────────────
    #  Check 2 — Head frozen
    # ─────────────────────────────────────────
    def _check_head_frozen(self, now: float) -> LivenessIssue | None:
        if len(self._nose_positions) < 5:
            return None

        positions = list(self._nose_positions)
        # Only examine positions in the freeze window
        freeze_cutoff  = now - self.config.HEAD_FREEZE_THRESHOLD
        recent = [(t, x, y) for t, x, y in positions if t >= freeze_cutoff]
        if len(recent) < 5:
            return None

        xs = [x for _, x, _ in recent]
        ys = [y for _, _, y in recent]
        max_disp = max(
            np.sqrt((x - xs[0])**2 + (y - ys[0])**2)
            for x, y in zip(xs, ys)
        )

        if max_disp >= self.config.HEAD_FREEZE_MIN_PX:
            return None
        if self._is_on_cooldown("HEAD_FROZEN", now):
            return None

        secs = int(self.config.HEAD_FREEZE_THRESHOLD)
        logger.warning(f"Liveness: head frozen for {secs}s (displacement={max_disp:.1f}px)")
        self._last_issue_time["HEAD_FROZEN"] = now

        return LivenessIssue(
            issue_type = "HEAD_FROZEN",
            severity   = "WARNING",
            message    = (
                f"No head movement detected for {secs} seconds. "
                "Please confirm you are present — move slightly or blink."
            ),
            confidence = round(1.0 - (max_disp / self.config.HEAD_FREEZE_MIN_PX), 2),
        )

    # ─────────────────────────────────────────
    #  Check 3 — Static frame (photo on screen)
    # ─────────────────────────────────────────
    def _check_static_frame(self, now: float) -> LivenessIssue | None:
        if len(self._frame_grays) < self.config.STATIC_FRAME_MIN_COUNT:
            return None
        if self._is_on_cooldown("STATIC_FRAME", now):
            return None

        frames   = [f for _, f in list(self._frame_grays)[-self.config.STATIC_FRAME_MIN_COUNT:]]
        diffs    = []
        for i in range(1, len(frames)):
            d = np.mean(np.abs(frames[i].astype(float) - frames[i-1].astype(float)))
            diffs.append(d)

        mean_diff = float(np.mean(diffs))
        if mean_diff > self.config.STATIC_FRAME_DIFF_THRESHOLD:
            return None

        logger.warning(f"Liveness: static frame detected (mean_diff={mean_diff:.3f})")
        self._last_issue_time["STATIC_FRAME"] = now

        return LivenessIssue(
            issue_type = "STATIC_FRAME",
            severity   = "HIGH",
            message    = (
                "Camera appears to be showing a static image. "
                "Please ensure your webcam is active and you are present."
            ),
            confidence = round(1.0 - (mean_diff / self.config.STATIC_FRAME_DIFF_THRESHOLD), 2),
        )

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────
    def _prune(self, dq: deque, cutoff: float):
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def _is_on_cooldown(self, issue_type: str, now: float) -> bool:
        last = self._last_issue_time.get(issue_type, 0.0)
        return (now - last) < self._COOLDOWN_SEC

    def reset(self):
        self._blink_scores.clear()
        self._nose_positions.clear()
        self._frame_grays.clear()
        self._last_blink_time   = time.time()
        self._blink_state       = "OPEN"
        self._last_issue_time   = {}
        self._frame_count       = 0
        logger.info("ContinuousLivenessMonitor reset")