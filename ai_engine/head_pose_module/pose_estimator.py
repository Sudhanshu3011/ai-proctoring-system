"""
head_pose_module/pose_estimator.py

AI-Based Intelligent Online Exam Proctoring System
Head Pose & Eye Gaze Tracking Module

FIX: Replaced deprecated mp.solutions.face_mesh with
     new MediaPipe Tasks API (FaceLandmarker)
     Compatible with mediapipe >= 0.10

Detects:
  - Yaw   (left/right head turn)
  - Pitch (up/down tilt)
  - Roll  (sideways tilt)
  - Gaze direction → violation flagging

Uses:
  - MediaPipe FaceLandmarker (Tasks API) -> 478 3D landmarks
  - OpenCV solvePnP                      -> 2D to 3D head orientation
  - Custom thresholds                    -> violation scoring
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

# ── New Tasks API imports (mediapipe >= 0.10) ─────────────────────────────
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

# ─────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Model path — adjust if your folder differs
# ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "face_landmarker.task")


# ─────────────────────────────────────────────
#  Configuration / Thresholds
# ─────────────────────────────────────────────
class PoseConfig:
    """All tunable thresholds in one place."""
    YAW_THRESHOLD   = 30    # degrees — head turned left/right
    PITCH_THRESHOLD = 20    # degrees — head tilted up/down
    ROLL_THRESHOLD  = 25    # degrees — head rolled sideways

    LOOK_AWAY_HOLD_SECONDS  = 2.0   # sustained look-away before violation fires
    VIOLATION_COOLDOWN      = 3.0   # seconds gap between repeated violations
    MAX_LOOKAWAY_PER_MINUTE = 10    # frequency anomaly threshold


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class HeadPoseResult:
    yaw:                float = 0.0
    pitch:              float = 0.0
    roll:               float = 0.0
    is_looking_away:    bool  = False
    direction:          str   = "FORWARD"   # FORWARD|LEFT|RIGHT|UP|DOWN|NO_FACE
    landmarks_detected: bool  = False
    confidence:         float = 0.0


@dataclass
class ViolationEvent:
    timestamp:        float
    yaw:              float
    pitch:            float
    roll:             float
    direction:        str
    duration_seconds: float = 0.0


@dataclass
class PoseSessionStats:
    total_violations:     int   = 0
    violation_events:     list  = field(default_factory=list)
    look_away_timestamps: list  = field(default_factory=list)
    last_violation_time:  float = 0.0
    look_away_start_time: Optional[float] = None


# ─────────────────────────────────────────────
#  3D canonical face model (mm)
#  Indices: Nose[1] Chin[152] LEye[263] REye[33] LMouth[287] RMouth[57]
# ─────────────────────────────────────────────
MODEL_POINTS_3D = np.array([
    (  0.0,    0.0,    0.0),
    (  0.0, -330.0,  -65.0),
    (-225.0,  170.0, -135.0),
    ( 225.0,  170.0, -135.0),
    (-150.0, -150.0, -125.0),
    ( 150.0, -150.0, -125.0),
], dtype=np.float64)

LANDMARK_INDICES = [1, 152, 263, 33, 287, 57]


# ─────────────────────────────────────────────
#  PoseEstimator
# ─────────────────────────────────────────────
class PoseEstimator:
    """
    Head pose estimator — new MediaPipe Tasks API (no mp.solutions).

    Quickstart:
        estimator = PoseEstimator()
        estimator.run_webcam()              # live demo

    Inside proctoring pipeline:
        result    = estimator.estimate_pose(bgr_frame)
        violation = estimator.check_violation(result)
        summary   = estimator.get_session_summary()   # for report_service
    """

    def __init__(self, config: PoseConfig = None, model_path: str = MODEL_PATH):
        self.config = config or PoseConfig()
        self.stats  = PoseSessionStats()

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"\n[PoseEstimator] Model not found: {model_path}\n"
                "Download it with:\n"
                "  mkdir -p ai_engine/head_pose_module/models\n"
                "  curl -o ai_engine/head_pose_module/models/face_landmarker.task \\\n"
                "    https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/latest/face_landmarker.task\n"
            )

        # ── FaceLandmarker via Tasks API ─────────────────────────────
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.landmarker = FaceLandmarker.create_from_options(options)
        logger.info(f"PoseEstimator ready. Model: {model_path}")

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────
    def _camera_matrix(self, shape) -> np.ndarray:
        h, w  = shape[:2]
        f     = float(w)
        return np.array([[f, 0, w/2.0],
                         [0, f, h/2.0],
                         [0, 0, 1.0  ]], dtype=np.float64)

    def _extract_2d(self, landmarks, w: int, h: int) -> np.ndarray:
        return np.array(
            [(landmarks[i].x * w, landmarks[i].y * h) for i in LANDMARK_INDICES],
            dtype=np.float64,
        )

    def _rvec_to_euler(self, rvec: np.ndarray):
        """Rodrigues vector -> (yaw, pitch, roll) in degrees."""
        R, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
        if sy > 1e-6:
            x = np.arctan2( R[2,1], R[2,2])
            y = np.arctan2(-R[2,0], sy)
            z = np.arctan2( R[1,0], R[0,0])
        else:
            x = np.arctan2(-R[1,2], R[1,1])
            y = np.arctan2(-R[2,0], sy)
            z = 0.0
        return np.degrees(y), np.degrees(x), np.degrees(z)  # yaw, pitch, roll

    def _direction(self, yaw: float, pitch: float) -> str:
        c = self.config
        if abs(yaw) <= c.YAW_THRESHOLD and abs(pitch) <= c.PITCH_THRESHOLD:
            return "FORWARD"
        if yaw < -c.YAW_THRESHOLD:  return "LEFT"
        if yaw >  c.YAW_THRESHOLD:  return "RIGHT"
        if pitch < -c.PITCH_THRESHOLD: return "DOWN"
        return "UP"

    # ─────────────────────────────────────────
    #  Core — one call per frame
    # ─────────────────────────────────────────
    def estimate_pose(self, frame: np.ndarray) -> HeadPoseResult:
        """
        Args:
            frame: BGR numpy array (from cv2.VideoCapture)
        Returns:
            HeadPoseResult
        """
        result = HeadPoseResult()
        h, w   = frame.shape[:2]

        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        detection = self.landmarker.detect(mp_image)

        if not detection.face_landmarks:
            result.direction = "NO_FACE"
            return result

        result.landmarks_detected = True
        lms = detection.face_landmarks[0]

        image_pts   = self._extract_2d(lms, w, h)
        cam_matrix  = self._camera_matrix(frame.shape)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        ok, rvec, tvec = cv2.solvePnP(
            MODEL_POINTS_3D, image_pts,
            cam_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            return result

        yaw, pitch, roll  = self._rvec_to_euler(rvec)
        dir_label         = self._direction(yaw, pitch)

        result.yaw             = round(yaw,   2)
        result.pitch           = round(pitch, 2)
        result.roll            = round(roll,  2)
        result.direction       = dir_label
        result.is_looking_away = (dir_label != "FORWARD")
        result.confidence      = 1.0

        self._draw_arrow(frame, rvec, tvec, cam_matrix, dist_coeffs,
                         result.is_looking_away)
        return result

    # ─────────────────────────────────────────
    #  Violation checker
    # ─────────────────────────────────────────
    def check_violation(self, result: HeadPoseResult) -> Optional[ViolationEvent]:
        """
        Hold-time + cooldown logic.
        Returns ViolationEvent when confirmed, else None.
        Feeds directly into risk_engine/scoring.py.
        """
        now = time.time()
        cfg = self.config

        if not result.is_looking_away:
            self.stats.look_away_start_time = None
            return None

        if self.stats.look_away_start_time is None:
            self.stats.look_away_start_time = now
            return None

        hold = now - self.stats.look_away_start_time

        if hold < cfg.LOOK_AWAY_HOLD_SECONDS:
            return None

        if (now - self.stats.last_violation_time) < cfg.VIOLATION_COOLDOWN:
            return None

        # ── Violation confirmed ──
        event = ViolationEvent(
            timestamp        = now,
            yaw              = result.yaw,
            pitch            = result.pitch,
            roll             = result.roll,
            direction        = result.direction,
            duration_seconds = round(hold, 2),
        )
        self.stats.total_violations        += 1
        self.stats.last_violation_time      = now
        self.stats.look_away_start_time     = None
        self.stats.violation_events.append(event)
        self.stats.look_away_timestamps.append(now)

        logger.warning(
            f"[VIOLATION] {event.direction} | "
            f"Yaw {event.yaw:+.1f}deg | Pitch {event.pitch:+.1f}deg | "
            f"Held {event.duration_seconds}s | Total #{self.stats.total_violations}"
        )
        return event

    # ─────────────────────────────────────────
    #  Risk + reporting helpers
    # ─────────────────────────────────────────
    def is_high_frequency_offender(self) -> bool:
        """True if look-aways > MAX_LOOKAWAY_PER_MINUTE in last 60 s."""
        cutoff = time.time() - 60.0
        recent = [t for t in self.stats.look_away_timestamps if t >= cutoff]
        return len(recent) > self.config.MAX_LOOKAWAY_PER_MINUTE

    def get_session_summary(self) -> dict:
        """Serialisable dict for report_service.py."""
        return {
            "total_violations":    self.stats.total_violations,
            "high_frequency_risk": self.is_high_frequency_offender(),
            "violation_events": [
                {
                    "timestamp":        e.timestamp,
                    "direction":        e.direction,
                    "yaw":              e.yaw,
                    "pitch":            e.pitch,
                    "roll":             e.roll,
                    "duration_seconds": e.duration_seconds,
                }
                for e in self.stats.violation_events
            ],
        }

    # ─────────────────────────────────────────
    #  Drawing helpers
    # ─────────────────────────────────────────
    def _draw_arrow(self, frame, rvec, tvec, cam_mat, dist, looking_away):
        p_nose, _ = cv2.projectPoints(np.array([[0.,0.,0.]]),   rvec, tvec, cam_mat, dist)
        p_tip,  _ = cv2.projectPoints(np.array([[0.,0.,100.]]), rvec, tvec, cam_mat, dist)
        color     = (0, 60, 255) if looking_away else (0, 230, 100)
        cv2.arrowedLine(frame,
                        tuple(p_nose[0][0].astype(int)),
                        tuple(p_tip[0][0].astype(int)),
                        color, 3, tipLength=0.3)

    def _draw_hud(self, frame, result: HeadPoseResult,
                  last_viol: Optional[ViolationEvent]):
        h, w = frame.shape[:2]
        ok   = (0, 230, 100)
        warn = (0, 180, 255)
        bad  = (0,  60, 255)
        ac   = bad if result.is_looking_away else ok

        cv2.rectangle(frame, (0, 0), (310, 152), (15, 15, 15), -1)
        cv2.putText(frame, f"YAW  : {result.yaw:+.1f}deg",  (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, ac, 2)
        cv2.putText(frame, f"PITCH: {result.pitch:+.1f}deg",(10, 58),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, ac, 2)
        cv2.putText(frame, f"ROLL : {result.roll:+.1f}deg", (10, 86),  cv2.FONT_HERSHEY_SIMPLEX, 0.6, ac, 2)
        cv2.putText(frame, f"DIR  : {result.direction}",    (10, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.6, ac, 2)
        cv2.putText(frame, f"VIOLATIONS: {self.stats.total_violations}",
                    (10, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.6, warn, 2)

        if last_viol:
            cv2.rectangle(frame, (0, h - 50), (w, h), (0, 0, 160), -1)
            cv2.putText(frame,
                        f"  VIOLATION: LOOKING {last_viol.direction}  ({last_viol.duration_seconds}s)",
                        (10, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        if self.is_high_frequency_offender():
            cv2.putText(frame, "! HIGH FREQUENCY RISK !",
                        (w // 2 - 160, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, bad, 2)

