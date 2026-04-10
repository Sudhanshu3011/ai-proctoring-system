"""
object_module/yolo_detector.py

AI-Based Intelligent Online Exam Proctoring System
Object Detection Module — YOLOv8 (fine-tuned)

Detects cheating-related objects:
  - cell_phone   (weight: 40 in risk engine)
  - book         (weight: 25)
  - headphone    (weight: 30)
  - earbud       (weight: 30)
  - person       (used for multi-person detection support)

Features added over sample code:
  - Auto model path resolution (no hardcoded paths)
  - Per-class confidence thresholds (your original logic kept)
  - IoU-based duplicate suppression (your original logic kept)
  - ViolationEvent dataclass  →  plugs into risk_engine/scoring.py
  - Session stats + summary   →  plugs into report_service.py
  - In-frame bounding box + label drawing
  - Violation cooldown (no spam)
  - Standalone webcam demo (python yolo_detector.py)
"""

import cv2
import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from ultralytics import YOLO

# ─────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Model path  — resolved relative to this file
# ─────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(BASE_DIR, "models", "finalBestV5.pt")


# ─────────────────────────────────────────────
#  Risk weights  (fed to risk_engine/scoring.py)
# ─────────────────────────────────────────────
VIOLATION_WEIGHTS = {
    "cell_phone" : 40,
    "book"       : 25,
    "headphone"  : 30,
    "earbud"     : 30,
}

# Visual colours per class  (BGR)
CLASS_COLORS = {
    "cell_phone" : (0,  60, 255),   # red
    "book"       : (0, 180, 255),   # orange
    "headphone"  : (180, 0, 255),   # purple
    "earbud"     : (255, 0, 180),   # pink
    "person"     : (0, 230, 100),   # green
}


# ─────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────
@dataclass
class Detection:
    """Single object detected in one frame."""
    cls:        str
    confidence: float
    bbox:       tuple       # (x1, y1, x2, y2)
    weight:     int = 0     # risk weight from VIOLATION_WEIGHTS


@dataclass
class ObjectViolationEvent:
    """Raised when a cheating object is confirmed detected."""
    timestamp:    float
    cls:          str
    confidence:   float
    bbox:         tuple
    weight:       int
    frame_path:   Optional[str] = None   # screenshot saved path


@dataclass
class ObjectSessionStats:
    total_violations:    int  = 0
    violation_events:    list = field(default_factory=list)
    last_violation_time: dict = field(default_factory=dict)  # per-class cooldown


# ─────────────────────────────────────────────
#  IoU helpers  (your original logic, unchanged)
# ─────────────────────────────────────────────
def compute_iou(boxA, boxB) -> float:
    """Intersection over Union for two (x1,y1,x2,y2) boxes."""
    xA = max(boxA[0], boxB[0]);  yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2]);  yB = min(boxA[3], boxB[3])
    inter_w  = max(0, xB - xA)
    inter_h  = max(0, yB - yA)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    aA = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    aB = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    return inter_area / float(aA + aB - inter_area)


def merge_by_class(detections: list, classes: set,
                   iou_threshold: float = 0.5) -> list:
    """
    For each class in `classes`, collapse overlapping boxes
    (IoU >= threshold) keeping the largest box per cluster.
    Boxes from other classes pass through unchanged.
    """
    final, used = [], set()
    grouped = {}
    for i, d in enumerate(detections):
        if d["class"] in classes:
            grouped.setdefault(d["class"], []).append((i, d))
        else:
            final.append(d)

    for cls, items in grouped.items():
        clusters = []
        for idx, det in items:
            if idx in used:
                continue
            used.add(idx)
            cluster = [det]
            for jdx, other in items:
                if jdx in used:
                    continue
                if compute_iou(det["bbox"], other["bbox"]) >= iou_threshold:
                    cluster.append(other)
                    used.add(jdx)
            clusters.append(cluster)

        for cluster in clusters:
            best = max(
                cluster,
                key=lambda d: (d["bbox"][2]-d["bbox"][0]) *
                              (d["bbox"][3]-d["bbox"][1])
            )
            final.append(best)
    return final


# ─────────────────────────────────────────────
#  ObjectDetector
# ─────────────────────────────────────────────
class ObjectDetector:
    """
    YOLOv8-based cheating object detector.

    Quickstart:
        detector = ObjectDetector()
        detector.run_webcam()               # live demo

    Inside proctoring pipeline:
        detections = detector.detect(bgr_frame)
        events     = detector.check_violations(detections, bgr_frame)
        summary    = detector.get_session_summary()
    """

    # ── cheating classes the model should care about ──────────────────
    CHEAT_CLASSES  = {"cell_phone", "book", "headphone", "earbud"}
    ALL_CLASSES    = CHEAT_CLASSES | {"person"}

    # ── per-class violation cooldown (seconds) ────────────────────────
    VIOLATION_COOLDOWN = {
        "cell_phone" : 5.0,
        "book"       : 8.0,
        "headphone"  : 8.0,
        "earbud"     : 8.0,
    }

    def __init__(
        self,
        model_path:   str   = MODEL_PATH,
        default_conf: float = 0.50,
        person_conf:  float = 0.40,
        phone_conf:   float = 0.60,
        book_conf:  float=0.70,
        audio_conf: float=0.50,  # headphones and earbuds often have lower confidence, so a lower threshold can help catch more without too many false positives 
        save_screenshots: bool  = True,
        screenshot_dir:   str   = "storage/screenshots/objects",
    ):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"\n[ObjectDetector] Model not found: {model_path}\n"
                f"Place your .pt file at:\n  {model_path}\n"
            )

        self.model        = YOLO(model_path)
        self.default_conf = default_conf
        self.person_conf  = person_conf
        self.stats        = ObjectSessionStats()

        self.save_screenshots = save_screenshots
        self.screenshot_dir   = screenshot_dir
        if save_screenshots:
            os.makedirs(screenshot_dir, exist_ok=True)

        # Per-class confidence thresholds (your original logic)
        self.class_thresholds = {
            "cell_phone" : phone_conf,
            "book"       : book_conf,
            "headphone"  : audio_conf,
            "earbud"     : audio_conf,
            "person"     : person_conf,
        }

        logger.info(f"ObjectDetector ready. Model: {model_path}")
        logger.info(f"Class thresholds: {self.class_thresholds}")

    # ─────────────────────────────────────────
    #  Internal — run model, filter, merge
    # ─────────────────────────────────────────
    def _run_model(self, frame) -> list:
        """
        Runs YOLO inference, applies per-class confidence filtering,
        then IoU-based duplicate merging.
        Returns list of raw dicts: {class, confidence, bbox}
        """
        raw = []
        results = self.model(frame, verbose=False)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                name   = self.model.names[cls_id]
                conf   = float(box.conf[0])

                if name not in self.ALL_CLASSES:
                    continue

                threshold = self.class_thresholds.get(name, self.default_conf)
                if conf < threshold:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                raw.append({
                    "class"     : name,
                    "confidence": round(conf, 3),
                    "bbox"      : (x1, y1, x2, y2),
                })

        # Suppress duplicate boxes per class
        merged = merge_by_class(raw, self.ALL_CLASSES, iou_threshold=0.5)
        return merged

    # ─────────────────────────────────────────
    #  Public — detect()
    # ─────────────────────────────────────────
    def detect(self, frame) -> list[Detection]:
        """
        Args:
            frame: BGR numpy array from cv2.VideoCapture

        Returns:
            List of Detection objects (empty if nothing found).
        """
        raw_dets = self._run_model(frame)
        detections = []
        for d in raw_dets:
            detections.append(Detection(
                cls        = d["class"],
                confidence = d["confidence"],
                bbox       = d["bbox"],
                weight     = VIOLATION_WEIGHTS.get(d["class"], 0),
            ))
        return detections

    # ─────────────────────────────────────────
    #  Public — check_violations()
    # ─────────────────────────────────────────
    def check_violations(
        self,
        detections: list[Detection],
        frame = None,
    ) -> list[ObjectViolationEvent]:
        """
        Converts detections into violation events with per-class cooldown.

        Args:
            detections: output of detect()
            frame:      optional BGR frame for saving screenshot evidence

        Returns:
            List of new ObjectViolationEvent (may be empty).
        """
        now    = time.time()
        events = []

        for det in detections:
            if det.cls not in self.CHEAT_CLASSES:
                continue

            last = self.stats.last_violation_time.get(det.cls, 0.0)
            cooldown = self.VIOLATION_COOLDOWN.get(det.cls, 5.0)

            if (now - last) < cooldown:
                continue    # still in cooldown for this class

            # ── Violation confirmed ──────────────────────────────────
            frame_path = None
            if self.save_screenshots and frame is not None:
                fname = (f"{det.cls}_{now:.0f}_"
                         f"conf{det.confidence:.2f}.jpg")
                frame_path = os.path.join(self.screenshot_dir, fname)
                cv2.imwrite(frame_path, frame)

            event = ObjectViolationEvent(
                timestamp  = now,
                cls        = det.cls,
                confidence = det.confidence,
                bbox       = det.bbox,
                weight     = det.weight,
                frame_path = frame_path,
            )
            self.stats.total_violations += 1
            self.stats.last_violation_time[det.cls] = now
            self.stats.violation_events.append(event)
            events.append(event)

            logger.warning(
                f"[VIOLATION] {det.cls.upper()} detected | "
                f"conf={det.confidence:.2f} | "
                f"weight={det.weight} | "
                f"total=#{self.stats.total_violations}"
            )

        return events

    # ─────────────────────────────────────────
    #  Risk engine integration
    # ─────────────────────────────────────────
    def get_risk_contribution(self) -> int:
        """
        Total raw risk score from object violations.
        Plugs into risk_engine/scoring.py as:
            total_score += detector.get_risk_contribution()
        """
        return sum(e.weight for e in self.stats.violation_events)

    # ─────────────────────────────────────────
    #  Report service integration
    # ─────────────────────────────────────────
    def get_session_summary(self) -> dict:
        """Serialisable dict consumed by report_service.py."""
        return {
            "total_violations" : self.stats.total_violations,
            "risk_contribution": self.get_risk_contribution(),
            "violation_events" : [
                {
                    "timestamp"  : e.timestamp,
                    "class"      : e.cls,
                    "confidence" : e.confidence,
                    "bbox"       : e.bbox,
                    "weight"     : e.weight,
                    "screenshot" : e.frame_path,
                }
                for e in self.stats.violation_events
            ],
        }

    # ─────────────────────────────────────────
    #  Drawing helpers
    # ─────────────────────────────────────────
    def draw_detections(self, frame, detections: list[Detection],
                        events: list[ObjectViolationEvent]):
        """Draw bounding boxes and labels on frame (in-place)."""
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color   = CLASS_COLORS.get(det.cls, (200, 200, 200))
            is_viol = any(e.cls == det.cls for e in events)

            # Box
            thickness = 3 if is_viol else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Label background
            label = f"{det.cls}  {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
            cv2.putText(frame, label, (x1 + 3, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Violation banner
        if events:
            names = ", ".join(set(e.cls for e in events)).upper()
            h, w  = frame.shape[:2]
            cv2.rectangle(frame, (0, h - 50), (w, h), (0, 0, 160), -1)
            cv2.putText(frame,
                        f"  VIOLATION DETECTED: {names}",
                        (10, h - 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    def _draw_hud(self, frame, detections, events):
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (280, 40), (15, 15, 15), -1)
        warn = (0, 180, 255)
        cv2.putText(frame,
                    f"OBJECTS  violations: {self.stats.total_violations}",
                    (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, warn, 2)
        self.draw_detections(frame, detections, events)

    # ─────────────────────────────────────────
    #  Standalone webcam demo
    # ─────────────────────────────────────────
    def run_webcam(self):
        """python yolo_detector.py  →  live demo, press ESC to quit."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Cannot open webcam.")
            return

        logger.info("Object Detector running. Press ESC to stop.")
        last_events = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detections  = self.detect(frame)
            last_events = self.check_violations(detections, frame)

            self._draw_hud(frame, detections, last_events)
            cv2.imshow("Object Detector", frame)

            if cv2.waitKey(1) & 0xFF == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

        s = self.get_session_summary()
        print("\n── Session Summary ──────────────────────────────────")
        print(f"  Total Violations  : {s['total_violations']}")
        print(f"  Risk Contribution : {s['risk_contribution']}")
        for i, e in enumerate(s["violation_events"], 1):
            print(f"  [{i}] {e['class'].upper():12s} | "
                  f"conf {e['confidence']:.2f} | "
                  f"weight {e['weight']} | "
                  f"screenshot: {e['screenshot']}")
        print("─────────────────────────────────────────────────────\n")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os
    os.environ["QT_QPA_PLATFORM"] = "xcb"   # Ubuntu/Wayland fix
    detector = ObjectDetector()
    detector.run_webcam()