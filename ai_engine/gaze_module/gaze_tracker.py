"""
ai_engine/gaze_module/gaze_tracker.py

Gaze Tracking — Where is the student looking on screen?

Uses MediaPipe FaceLandmarker iris landmarks (landmarks 468-477)
to estimate the gaze direction and map it to a screen region.

Screen regions:
    ┌──────┬──────┬──────┐
    │ TL   │  TC  │  TR  │
    ├──────┼──────┼──────┤
    │  CL  │ CENTER│  CR  │
    ├──────┼──────┼──────┤
    │  BL  │  BC  │  BR  │
    └──────┴──────┴──────┘

Why this matters:
    - Looking at screen corners frequently = checking notes
    - Repeatedly looking off-screen left/right = second monitor
    - Gaze heatmap shows attention distribution in report

Output:
    - Per-frame gaze region
    - Session heatmap (9-cell grid with dwell percentages)
    - Off-screen event count
"""

import cv2
import numpy as np
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GazeFrame:
    timestamp   : float
    region      : str         # TL|TC|TR|CL|CENTER|CR|BL|BC|BR|OFF_SCREEN
    gaze_x      : float       # normalised 0.0–1.0 (0=left, 1=right)
    gaze_y      : float       # normalised 0.0–1.0 (0=top, 1=bottom)
    confidence  : float


@dataclass
class GazeSessionData:
    """Accumulated gaze data for a session — stored and included in report."""
    region_counts    : dict   = field(default_factory=dict)
    region_pct       : dict   = field(default_factory=dict)
    off_screen_count : int    = 0
    off_screen_pct   : float  = 0.0
    corner_pct       : float  = 0.0   # TL+TR+BL+BR combined
    dominant_region  : str    = "CENTER"
    suspicion_note   : str    = ""

    def to_dict(self) -> dict:
        return {
            "region_counts"   : {k: int(v) for k, v in self.region_counts.items()},
            "region_pct"      : {k: float(round(v, 1)) for k, v in self.region_pct.items()},
            "off_screen_count": int(self.off_screen_count),
            "off_screen_pct"  : float(round(self.off_screen_pct, 1)),
            "corner_pct"      : float(round(self.corner_pct, 1)),
            "dominant_region" : str(self.dominant_region),
            "suspicion_note"  : str(self.suspicion_note),
        }


class GazeTracker:
    """
    Real-time gaze tracker using iris landmarks.

    Usage:
        tracker = GazeTracker()

        # Each frame (during exam):
        gaze = tracker.update(frame)
        if gaze.region == "OFF_SCREEN":
            # flag it

        # End of exam:
        summary = tracker.get_session_summary()
    """

    # Screen regions (3x3 grid)
    REGIONS = {
        (0,0):'TL', (1,0):'TC', (2,0):'TR',
        (0,1):'CL', (1,1):'CENTER', (2,1):'CR',
        (0,2):'BL', (1,2):'BC', (2,2):'BR',
    }
    CORNERS = {'TL','TR','BL','BR'}
    OFF_THRESHOLD = 0.12   # gaze within 12% of edge = possible off-screen

    def __init__(self, model_path: str = None):
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
                model_path = os.path.join(
                    base, '..', 'face_module', 'models', 'face_landmarker.task'
                )
            options = FaceLandmarkerOptions(
                base_options  = BaseOptions(model_asset_path=model_path),
                running_mode  = RunningMode.IMAGE,
                num_faces     = 1,
                min_face_detection_confidence = 0.4,
                output_face_blendshapes       = False,
            )
            self._landmarker = FaceLandmarker.create_from_options(options)
            logger.info("GazeTracker: landmarker loaded")
        except Exception as e:
            logger.warning(f"GazeTracker: landmarker unavailable ({e})")

        # Session history
        self._history   : list[GazeFrame] = []
        self._counts    : dict[str,int]   = defaultdict(int)
        self._frame_n   = 0

    def update(self, frame: np.ndarray) -> GazeFrame:
        """Process one frame and return gaze result."""
        self._frame_n += 1
        now = time.time()

        if self._landmarker is None:
            # Fallback: estimate gaze from head pose only
            return self._fallback_gaze(frame, now)

        try:
            import mediapipe as mp
            rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result   = self._landmarker.detect(mp_image)

            if not result.face_landmarks:
                gaze = GazeFrame(
                    timestamp  = now,
                    region     = "OFF_SCREEN",
                    gaze_x     = -1.0,
                    gaze_y     = -1.0,
                    confidence = 0.0,
                )
                self._record(gaze)
                return gaze

            lms = result.face_landmarks[0]

            # Iris landmarks: left iris center = lm 468, right iris center = lm 473
            # These are only available when face_landmarker.task supports them
            if len(lms) > 473:
                left_iris  = lms[468]
                right_iris = lms[473]
                iris_x     = (left_iris.x + right_iris.x) / 2
                iris_y     = (left_iris.y + right_iris.y) / 2
            else:
                # Fallback: use eye corner midpoints (landmarks 33, 133, 362, 263)
                eye_points = [lms[i] for i in [33, 133, 362, 263] if i < len(lms)]
                if not eye_points:
                    return self._fallback_gaze(frame, now)
                iris_x = float(np.mean([p.x for p in eye_points]))
                iris_y = float(np.mean([p.y for p in eye_points]))

            # Map iris position to screen region
            region, gaze_x, gaze_y = self._map_to_region(iris_x, iris_y)

            gaze = GazeFrame(
                timestamp  = now,
                region     = region,
                gaze_x     = float(round(gaze_x, 3)),
                gaze_y     = float(round(gaze_y, 3)),
                confidence = 0.85,
            )
            self._record(gaze)
            return gaze

        except Exception as e:
            logger.debug(f"GazeTracker update error: {e}")
            return self._fallback_gaze(frame, now)

    def _fallback_gaze(self, frame: np.ndarray, now: float) -> GazeFrame:
        """Fallback when landmarker not available — use face position."""
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces   = cascade.detectMultiScale(gray, 1.1, 4)
        h, w    = frame.shape[:2]

        if len(faces) == 0:
            g = GazeFrame(now, "OFF_SCREEN", -1.0, -1.0, 0.3)
            self._record(g)
            return g

        x, y, fw, fh = faces[0]
        cx = (x + fw / 2) / w
        cy = (y + fh / 2) / h
        region, gx, gy = self._map_to_region(cx, cy)
        g = GazeFrame(now, region, float(round(gx, 3)), float(round(gy, 3)), 0.5)
        self._record(g)
        return g

    def _map_to_region(self, x: float, y: float) -> tuple[str, float, float]:
        """Map normalised (x,y) to 3x3 grid region."""
        # Off-screen check
        if x < self.OFF_THRESHOLD or x > (1 - self.OFF_THRESHOLD) or \
           y < self.OFF_THRESHOLD or y > (1 - self.OFF_THRESHOLD):
            return "OFF_SCREEN", float(x), float(y)

        col = min(2, int(x * 3))
        row = min(2, int(y * 3))
        return self.REGIONS.get((col, row), "CENTER"), float(x), float(y)

    def _record(self, gaze: GazeFrame):
        self._history.append(gaze)
        self._counts[gaze.region] += 1

    def get_session_summary(self) -> GazeSessionData:
        """Return accumulated gaze analytics for the session."""
        total = max(len(self._history), 1)
        pcts  = {r: float(round(c / total * 100, 1)) for r, c in self._counts.items()}

        off_count = int(self._counts.get("OFF_SCREEN", 0))
        off_pct   = float(round(off_count / total * 100, 1))

        corner_pct = float(sum(
            self._counts.get(r, 0) for r in self.CORNERS
        ) / total * 100)

        dominant = max(self._counts, key=self._counts.get, default="CENTER")

        # Suspicion heuristics
        note = ""
        if off_pct > 25:
            note = f"High off-screen gaze ({off_pct:.0f}%). Possible second monitor or reference material."
        elif corner_pct > 30:
            note = f"Frequent corner gaze ({corner_pct:.0f}%). Possible notes or secondary screen in corners."
        elif dominant == "OFF_SCREEN":
            note = "Gaze was predominantly off-screen during the exam."

        return GazeSessionData(
            region_counts    = dict(self._counts),
            region_pct       = pcts,
            off_screen_count = off_count,
            off_screen_pct   = off_pct,
            corner_pct       = float(round(corner_pct, 1)),
            dominant_region  = str(dominant),
            suspicion_note   = note,
        )

    def reset(self):
        self._history.clear()
        self._counts.clear()
        self._frame_n = 0
        logger.info("GazeTracker reset")