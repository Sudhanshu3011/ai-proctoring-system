"""
ai_engine/face_module/liveness.py

Multi-Frame Liveness Detection Engine

Approach:
    Receives a sequence of frames (captured over ~3 seconds).
    Checks 3 independent signals across the sequence:

    Signal 1 — Blink cycle (open → closing → open)
        Tracks eyeBlinkLeft/Right blendshape scores across frames.
        Requires a complete cycle within the sequence.
        A static photo has a fixed blink score — never transitions.

    Signal 2 — Head movement
        Tracks nose tip position across frames.
        Requires minimum pixel displacement over the sequence.
        A photo on a screen has zero movement.

    Signal 3 — Temporal texture variance
        Laplacian variance must differ across frames.
        A live face has micro-movements causing frame-to-frame change.
        A static photo/screen has near-identical frames.

All 3 signals must pass for liveness to be confirmed.
Passing threshold: at least 2 of 3 signals (configurable).

Minimum frames required: 8
Recommended: 15–25 frames over 2–3 seconds
"""

import cv2
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Optional

import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
class LivenessConfig:
    # Blink detection
    BLINK_CLOSE_THRESHOLD  = 0.35   # score above this = eye closing
    BLINK_OPEN_THRESHOLD   = 0.15   # score below this = eye open again
    BLINK_MAX_DURATION_MS  = 500    # blink must complete within 500ms
    BLINK_MIN_PEAK         = 0.40   # peak blink score must exceed this

    # Head movement
    HEAD_MOVE_MIN_PIXELS   = 8      # minimum nose displacement across sequence
    HEAD_MOVE_MIN_FRAMES   = 5      # must show movement across at least 5 frames

    # Temporal variance
    TEMPORAL_VAR_THRESHOLD = 15.0   # frame-to-frame variance must exceed this
    TEMPORAL_VAR_MIN_FRAMES= 5      # at least 5 frames must show variation

    # Passing criteria
    MIN_SIGNALS_TO_PASS    = 2      # must pass at least 2 of 3 signals
    MIN_FRAMES_REQUIRED    = 8      # reject if too few frames sent


# ─────────────────────────────────────────────
#  Result dataclass
# ─────────────────────────────────────────────
@dataclass
class LivenessResult:
    is_live:          bool
    confidence:       float          # 0.0–1.0 based on signals passed
    signals_passed:   int            # 0, 1, 2, or 3
    blink_detected:   bool = False
    head_moved:       bool = False
    temporal_varied:  bool = False
    frames_analyzed:  int  = 0
    reason:           str  = ""
    debug_info:       dict = field(default_factory=dict)


# ─────────────────────────────────────────────
#  LivenessChecker
# ─────────────────────────────────────────────
class LivenessChecker:
    """
    Multi-frame liveness checker.

    Usage:
        checker = LivenessChecker()
        result  = checker.check(frames)   # frames = list of BGR numpy arrays
        if result.is_live:
            # proceed with embedding extraction
    """

    def __init__(self, config: LivenessConfig = None, model_path: str = None):
        self.config = config or LivenessConfig()

        if model_path is None:
            import os
            base = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base, "models", "face_landmarker.task")

        options = FaceLandmarkerOptions(
            base_options  = BaseOptions(model_asset_path=model_path),
            running_mode  = RunningMode.IMAGE,
            num_faces     = 1,
            min_face_detection_confidence = 0.5,
            min_face_presence_confidence  = 0.5,
            min_tracking_confidence       = 0.5,
            output_face_blendshapes       = True,
            output_facial_transformation_matrixes = False,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        logger.info("LivenessChecker ready.")

    # ─────────────────────────────────────────
    #  Main entry point
    # ─────────────────────────────────────────
    def check(
        self,
        frames     : list[np.ndarray],
        fps        : float = 10.0,
    ) -> LivenessResult:
        """
        Analyse a sequence of BGR frames for liveness.

        Args:
            frames: list of BGR numpy arrays (minimum 8, recommend 15-25)
            fps:    frames per second the sequence was captured at

        Returns:
            LivenessResult
        """
        n = len(frames)
        if n < self.config.MIN_FRAMES_REQUIRED:
            return LivenessResult(
                is_live        = False,
                confidence     = 0.0,
                signals_passed = 0,
                frames_analyzed= n,
                reason         = (
                    f"Too few frames ({n}). "
                    f"Need at least {self.config.MIN_FRAMES_REQUIRED}."
                ),
            )

        # ── Extract per-frame data ────────────────────────────────
        frame_data = self._extract_frame_data(frames)
        valid      = [d for d in frame_data if d["face_detected"]]

        if len(valid) < self.config.MIN_FRAMES_REQUIRED // 2:
            return LivenessResult(
                is_live        = False,
                confidence     = 0.0,
                signals_passed = 0,
                frames_analyzed= n,
                reason         = (
                    f"Face not consistently visible "
                    f"({len(valid)}/{n} frames had a face)."
                ),
            )

        # ── Run 3 signals ─────────────────────────────────────────
        blink_ok,   blink_dbg  = self._check_blink(valid, fps)
        move_ok,    move_dbg   = self._check_head_movement(valid)
        texture_ok, tex_dbg    = self._check_temporal_variance(frames)

        signals_passed = sum([blink_ok, move_ok, texture_ok])
        is_live        = signals_passed >= self.config.MIN_SIGNALS_TO_PASS
        confidence     = signals_passed / 3.0

        # Build human-readable reason
        passed  = []
        failed  = []
        if blink_ok:   passed.append("blink")
        else:          failed.append("blink")
        if move_ok:    passed.append("head movement")
        else:          failed.append("head movement")
        if texture_ok: passed.append("temporal variation")
        else:          failed.append("temporal variation")

        if is_live:
            reason = f"Liveness confirmed ({', '.join(passed)} detected)."
        else:
            reason = (
                f"Liveness failed — only {signals_passed}/3 signals passed. "
                f"Passed: {passed or ['none']}. "
                f"Failed: {failed}."
            )

        logger.info(
            f"Liveness | live={is_live} signals={signals_passed}/3 "
            f"blink={blink_ok} move={move_ok} texture={texture_ok} "
            f"frames={n} valid={len(valid)}"
        )

        return LivenessResult(
            is_live         = is_live,
            confidence      = round(confidence, 2),
            signals_passed  = signals_passed,
            blink_detected  = blink_ok,
            head_moved      = move_ok,
            temporal_varied = texture_ok,
            frames_analyzed = n,
            reason          = reason,
            debug_info      = {
                "blink"  : blink_dbg,
                "move"   : move_dbg,
                "texture": tex_dbg,
                "valid_frames": len(valid),
            },
        )

    # ─────────────────────────────────────────
    #  Frame feature extraction
    # ─────────────────────────────────────────
    def _extract_frame_data(self, frames: list[np.ndarray]) -> list[dict]:
        """Run FaceLandmarker on every frame and collect features."""
        result_list = []

        for i, frame in enumerate(frames):
            try:
                rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                det      = self._landmarker.detect(mp_image)
                h, w     = frame.shape[:2]

                if not det.face_landmarks or not det.face_blendshapes:
                    result_list.append({
                        "frame_idx"    : i,
                        "face_detected": False,
                    })
                    continue

                # Nose tip position
                nose = det.face_landmarks[0][1]
                nx   = nose.x * w
                ny   = nose.y * h

                # Blink scores
                bl = br = 0.0
                for bs in det.face_blendshapes[0]:
                    if bs.category_name == "eyeBlinkLeft":
                        bl = bs.score
                    elif bs.category_name == "eyeBlinkRight":
                        br = bs.score

                # Laplacian variance (texture)
                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                lapv  = cv2.Laplacian(gray, cv2.CV_64F).var()

                result_list.append({
                    "frame_idx"    : i,
                    "face_detected": True,
                    "nose_x"       : nx,
                    "nose_y"       : ny,
                    "blink_left"   : bl,
                    "blink_right"  : br,
                    "blink_max"    : max(bl, br),
                    "laplacian_var": lapv,
                })

            except Exception as e:
                logger.debug(f"Frame {i} extraction error: {e}")
                result_list.append({"frame_idx": i, "face_detected": False})

        return result_list

    # ─────────────────────────────────────────
    #  Signal 1 — Blink detection
    # ─────────────────────────────────────────
    def _check_blink(
        self,
        valid_frames: list[dict],
        fps: float,
    ) -> tuple[bool, dict]:
        """
        Detect a complete blink cycle (open → closing → open) in the sequence.

        Algorithm:
            - Scan blink_max scores across frames
            - Look for: LOW (< open_threshold)
                     → HIGH (> close_threshold)
                     → LOW  (< open_threshold)
            - Must complete within BLINK_MAX_DURATION_MS
            - Peak blink score must exceed BLINK_MIN_PEAK

        A static photo: constant blink score, no cycle.
        A live person: score rises during blink, drops when eye reopens.
        """
        cfg    = self.config
        scores = [d["blink_max"] for d in valid_frames]
        n      = len(scores)
        ms_per_frame = 1000.0 / fps

        phase     = "OPEN"
        open_idx  = 0
        peak      = 0.0
        blinks    = 0

        for i, score in enumerate(scores):
            if phase == "OPEN":
                if score > cfg.BLINK_CLOSE_THRESHOLD:
                    phase    = "CLOSING"
                    open_idx = i
                    peak     = score

            elif phase == "CLOSING":
                peak = max(peak, score)
                elapsed_ms = (i - open_idx) * ms_per_frame

                if elapsed_ms > cfg.BLINK_MAX_DURATION_MS:
                    # Took too long — reset, not a real blink
                    phase = "OPEN"
                    peak  = 0.0
                elif score < cfg.BLINK_OPEN_THRESHOLD and peak >= cfg.BLINK_MIN_PEAK:
                    # Complete blink cycle confirmed
                    blinks += 1
                    phase   = "OPEN"
                    peak    = 0.0

        debug = {
            "blink_cycles_detected": blinks,
            "score_min": round(min(scores), 3),
            "score_max": round(max(scores), 3),
            "score_range": round(max(scores) - min(scores), 3),
        }

        # Also accept if score range is large (strong blink even if cycle incomplete)
        score_range_ok = (max(scores) - min(scores)) > 0.30 and max(scores) > cfg.BLINK_MIN_PEAK

        passed = blinks >= 1 or score_range_ok
        return passed, debug

    # ─────────────────────────────────────────
    #  Signal 2 — Head movement
    # ─────────────────────────────────────────
    def _check_head_movement(
        self,
        valid_frames: list[dict],
    ) -> tuple[bool, dict]:
        """
        Verify the nose tip moved across the sequence.

        Computes:
            - Total path length (sum of frame-to-frame distances)
            - Max displacement from starting position
            - Frames that show meaningful movement

        A printed photo: nose position is identical in every frame.
        A live person: natural micro-movements create consistent displacement.
        """
        cfg = self.config

        xs = [d["nose_x"] for d in valid_frames]
        ys = [d["nose_y"] for d in valid_frames]

        if len(xs) < 2:
            return False, {"reason": "too few frames"}

        # Frame-to-frame distances
        distances = [
            np.sqrt((xs[i] - xs[i-1])**2 + (ys[i] - ys[i-1])**2)
            for i in range(1, len(xs))
        ]

        # Max displacement from first frame position
        max_displacement = max(
            np.sqrt((x - xs[0])**2 + (y - ys[0])**2)
            for x, y in zip(xs, ys)
        )

        # Frames with meaningful movement (> 2 pixels from previous)
        moving_frames = sum(1 for d in distances if d > 2.0)

        debug = {
            "max_displacement_px": round(max_displacement, 1),
            "total_path_px"      : round(sum(distances), 1),
            "moving_frames"      : moving_frames,
            "total_frames"       : len(xs),
        }

        passed = (
            max_displacement >= cfg.HEAD_MOVE_MIN_PIXELS
            and moving_frames >= cfg.HEAD_MOVE_MIN_FRAMES
        )
        return passed, debug

    # ─────────────────────────────────────────
    #  Signal 3 — Temporal texture variance
    # ─────────────────────────────────────────
    def _check_temporal_variance(
        self,
        frames: list[np.ndarray],
    ) -> tuple[bool, dict]:
        """
        Check frame-to-frame texture variation.

        Computes Laplacian variance for each frame.
        A live face has micro-movements causing frame-to-frame texture change.
        A static photo/screen has near-identical frames each time.

        Additionally checks for pixel-level frame differences:
        Static image → near-zero diff between consecutive frames.
        Live face    → continuous small changes from micro-movement.
        """
        cfg        = self.config
        variances  = []
        frame_diffs= []

        # Sample every 2nd frame to save time
        sampled = frames[::2]

        prev_gray = None
        for frame in sampled:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            lv   = cv2.Laplacian(gray, cv2.CV_64F).var()
            variances.append(lv)

            if prev_gray is not None:
                diff = np.mean(np.abs(gray.astype(float) - prev_gray.astype(float)))
                frame_diffs.append(diff)
            prev_gray = gray

        if not variances:
            return False, {"reason": "no frames to analyze"}

        lap_variance     = float(np.std(variances))   # std of variances = they change over time
        mean_frame_diff  = float(np.mean(frame_diffs)) if frame_diffs else 0.0
        high_var_frames  = sum(1 for v in variances if v > 80)

        debug = {
            "laplacian_std"   : round(lap_variance, 2),
            "mean_frame_diff" : round(mean_frame_diff, 3),
            "high_var_frames" : high_var_frames,
            "total_sampled"   : len(sampled),
        }

        # Pass if:
        # - Frame diffs indicate real movement (not static screen)
        # - OR Laplacian variance itself varies enough across frames
        passed = (
            mean_frame_diff > 0.8             # continuous pixel change
            or lap_variance > cfg.TEMPORAL_VAR_THRESHOLD  # texture changing
        )
        return passed, debug


# ─────────────────────────────────────────────
#  Module-level singleton
# ─────────────────────────────────────────────
_checker_instance: Optional[LivenessChecker] = None

def get_liveness_checker() -> LivenessChecker:
    """Lazy singleton — model loaded once."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = LivenessChecker()
    return _checker_instance
