"""
ai_engine/face_module/detector.py

Face Detection Module — AI Proctoring System

Pipeline per call:
    Webcam frame
        │
        ├── MediaPipe FaceDetector   → find face bbox (blaze_face_short_range.tflite)
        │       ├── No face    → log + retry
        │       └── Multi face → log violation + retry
        │
        ├── FaceLandmarker           → 478 landmarks + blendshapes for liveness
        │       ├── eyeBlinkLeft / eyeBlinkRight  blendshape scores
        │       └── Nose tip movement across frames (head motion)
        │
        └── InceptionResnetV1        → 512-d face embedding (FaceNet / vggface2)

Returns:
    {
        "message":          "Face Detected",
        "image_base64":     "<jpeg bytes as base64>",
        "embedding_base64": "<float32 numpy bytes as base64>"
    }

Fixes applied over original code:
  1. mp.solutions.face_mesh  → FaceLandmarker Tasks API (mediapipe >= 0.10)
  2. Blendshape-based blink  → eyeBlinkLeft score > threshold (far more accurate)
  3. Camera opened inside function, not at module level
  4. Dead code after return removed
  5. Face crop size validation added
  6. Proper EAR-equivalent blink using blendshape scores
"""

import cv2
import mediapipe as mp
import os
import numpy as np
import base64
import time
import torch
from io import BytesIO
from PIL import Image as PILImage
from facenet_pytorch import InceptionResnetV1

# New Tasks API imports (mediapipe >= 0.10)
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceDetector,
    FaceDetectorOptions,
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

from ai_engine.logger import get_logger

# ─────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────
logger = get_logger("face_detector")
logger.info("Detector module loading...")

# ─────────────────────────────────────────────
#  Model paths
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FACE_DETECT_MODEL = os.path.abspath(
    os.path.join(BASE_DIR, "models", "blaze_face_short_range.tflite")
)
FACE_LANDMARK_MODEL = os.path.abspath(
    os.path.join(BASE_DIR, "models", "face_landmarker.task")
)

logger.info(f"FaceDetector model  : {FACE_DETECT_MODEL}")
logger.info(f"FaceLandmarker model: {FACE_LANDMARK_MODEL}")
logger.info(f"Detector exists     : {os.path.exists(FACE_DETECT_MODEL)}")
logger.info(f"Landmarker exists   : {os.path.exists(FACE_LANDMARK_MODEL)}")


# ─────────────────────────────────────────────
#  Liveness config
# ─────────────────────────────────────────────

# Tracks blink state across frames — persists between calls
_blink_state = {
    "phase":         "OPEN",     # OPEN → CLOSING → BLINK_CONFIRMED
    "confirmed":     False,
    "close_time":    None,
}

BLINK_CLOSE_THRESHOLD = 0.35    # score above this = eye closing
BLINK_OPEN_THRESHOLD  = 0.15    # score below this = eye fully open again
BLINK_MAX_DURATION    = 0.4     # seconds — blink must complete within this
BLINK_SCORE_THRESHOLD  = 0.35    # blendshape score above this = eye closed
HEAD_MOVE_MIN_PIXELS   = 4       # pixels of nose movement = head moved
LIVENESS_TIMEOUT_SEC   = 5       # seconds without confirmed liveness → log error


# ─────────────────────────────────────────────
#  Device
# ─────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Torch device: {device}")


# ─────────────────────────────────────────────
#  Load models (module level — loaded ONCE)
# ─────────────────────────────────────────────

# ── 1. MediaPipe Face Detector (Tasks API) ────────────────────────
_detect_options = FaceDetectorOptions(
    base_options = BaseOptions(model_asset_path=FACE_DETECT_MODEL),
    running_mode = RunningMode.IMAGE,
    min_detection_confidence = 0.6,
)
detector = FaceDetector.create_from_options(_detect_options)
logger.info("FaceDetector loaded.")

# ── 2. FaceLandmarker with blendshapes (Tasks API) ────────────────
# Blendshapes give us eyeBlinkLeft / eyeBlinkRight scores (0–1)
# This replaces the old mp.solutions.face_mesh which is removed in >= 0.10
_landmark_options = FaceLandmarkerOptions(
    base_options = BaseOptions(model_asset_path=FACE_LANDMARK_MODEL),
    running_mode = RunningMode.IMAGE,
    num_faces    = 1,
    min_face_detection_confidence = 0.5,
    min_face_presence_confidence  = 0.5,
    min_tracking_confidence       = 0.5,
    output_face_blendshapes       = True,   # ← needed for blink detection
    output_facial_transformation_matrixes = False,
)
landmarker = FaceLandmarker.create_from_options(_landmark_options)
logger.info("FaceLandmarker (blendshapes) loaded.")

# ── 3. FaceNet — InceptionResnetV1 ───────────────────────────────
inception_resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
logger.info("InceptionResnetV1 (vggface2) loaded.")


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def preprocess_face(face_img: np.ndarray) -> torch.Tensor:
    """
    Prepare a BGR face crop for InceptionResnetV1.
    Returns a (1, 3, 160, 160) float32 tensor on the correct device.
    """
    face_img = cv2.resize(face_img, (160, 160))
    face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

    face_tensor = torch.from_numpy(face_img).float()   # (H, W, C)
    face_tensor = face_tensor.permute(2, 0, 1)         # → (C, H, W)
    face_tensor = face_tensor / 255.0                  # normalize 0–1
    face_tensor = face_tensor.unsqueeze(0).to(device)  # → (1, C, H, W)

    return face_tensor


def check_liveness(
    frame: np.ndarray,
    prev_center: tuple | None,
) -> tuple[bool, tuple | None]:
    """
    Two-signal liveness check using FaceLandmarker blendshapes.

    Signal 1 — Head movement:
        Tracks nose tip (landmark 1) across frames.
        If nose moved > HEAD_MOVE_MIN_PIXELS pixels → alive.

    Signal 2 — Blink detection (blendshapes):
        eyeBlinkLeft or eyeBlinkRight blendshape score > BLINK_SCORE_THRESHOLD
        → eye is closing/closed → genuine blink detected.
        This is FAR more accurate than comparing raw y-coordinates of two
        different eye landmarks (which was the original approach).

    Args:
        frame:       BGR numpy frame from webcam
        prev_center: (x, y) nose position from previous call, or None

    Returns:
        (is_live, current_nose_center)
    """
    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    result = landmarker.detect(mp_image)

    if not result.face_landmarks or not result.face_blendshapes:
        return False, prev_center

    # ── Signal 1: Head movement ───────────────────────────────────
    h, w = frame.shape[:2]
    landmarks = result.face_landmarks[0]
    nose      = landmarks[1]                      # nose tip index
    cx        = int(nose.x * w)
    cy        = int(nose.y * h)

    moved = True
    if prev_center is not None:
        dist  = np.sqrt((cx - prev_center[0]) ** 2 + (cy - prev_center[1]) ** 2)
        moved = dist > HEAD_MOVE_MIN_PIXELS

    # ── Signal 2: Full blink cycle detection (OPEN → CLOSED → OPEN) ──
    # A single frame with eyes slightly closed is NOT a blink.
    # We require the complete cycle to confirm liveness.
    blendshapes = result.face_blendshapes[0]
    blink_left  = 0.0
    blink_right = 0.0

    for bs in blendshapes:
        if bs.category_name == "eyeBlinkLeft":
            blink_left  = bs.score
        elif bs.category_name == "eyeBlinkRight":
            blink_right = bs.score

    # Use the higher of the two eyes
    blink_score = max(blink_left, blink_right)
    now         = time.time()

    if _blink_state["phase"] == "OPEN":
        # Waiting for eye to start closing
        if blink_score > BLINK_CLOSE_THRESHOLD:
            _blink_state["phase"]      = "CLOSING"
            _blink_state["close_time"] = now
            logger.debug(f"Blink started (score={blink_score:.2f})")

    elif _blink_state["phase"] == "CLOSING":
        # Eye was closing — now waiting for it to reopen
        elapsed = now - _blink_state["close_time"]

        if elapsed > BLINK_MAX_DURATION:
            # Took too long — probably just looking down, not a real blink
            _blink_state["phase"] = "OPEN"
            logger.debug("Blink timeout — resetting state")

        elif blink_score < BLINK_OPEN_THRESHOLD:
            # Eye closed AND reopened within time window → confirmed blink
            _blink_state["phase"]     = "OPEN"
            _blink_state["confirmed"] = True
            logger.info(f"BLINK CONFIRMED (duration={elapsed:.2f}s)")

    blinked = _blink_state["confirmed"]
    is_live = moved and blinked

    logger.debug(
        f"Liveness | nose=({cx},{cy}) moved={moved} "
        f"blinkL={blink_left:.2f} blinkR={blink_right:.2f} "
        f"blinked={blinked} → live={is_live}"
    )

    return is_live, (cx, cy)


# ─────────────────────────────────────────────
#  Main detection function
# ─────────────────────────────────────────────
def faceDetection() -> dict | None:
    """
    Captures frames from webcam until a live, single, verified face
    is detected and returns its embedding.

    Returns:
        {
            "message":          "Face Detected",
            "image_base64":     str,   # JPEG face crop as base64
            "embedding_base64": str,   # float32 FaceNet embedding as base64
        }
        or None if camera fails.

    Note:
        Camera is opened and released INSIDE this function.
        Never at module level — safe to call multiple times.
    """
    # ── Open camera inside the function ──────────────────────────
    # This is intentional — opening at module level keeps the camera
    # locked even when the function is not running.
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Cannot open webcam.")
        return None

    logger.info("Camera opened. Waiting for live face...")

    liveness_start = time.time()
    prev_center    = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to read frame from camera.")
                break

            rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            result = detector.detect(mp_image)

            # ── No face detected ──────────────────────────────────
            if not result.detections:
                if time.time() - liveness_start > LIVENESS_TIMEOUT_SEC:
                    logger.error("No face detected for 5s — retrying window.")
                    liveness_start = time.time()

                cv2.imshow("Face Detector", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
                continue

            # ── Multiple faces → cheating risk ───────────────────
            if len(result.detections) > 1:
                logger.warning(
                    f"MULTIPLE FACES DETECTED ({len(result.detections)}) "
                    "— cheating risk flagged"
                )
                cv2.imshow("Face Detector", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
                continue

            # ── Single face detected ──────────────────────────────
            detection = result.detections[0]
            bbox = detection.bounding_box

            x = max(0, int(bbox.origin_x))
            y = max(0, int(bbox.origin_y))
            fw = int(bbox.width)
            fh = int(bbox.height)

            face_image = frame[y:y + fh, x:x + fw]

            # Validate crop — skip if too small or empty
            if face_image.size == 0 or fw < 40 or fh < 40:
                logger.debug("Face crop too small — skipping frame.")
                cv2.imshow("Face Detector", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
                continue

            # ── Liveness check ────────────────────────────────────
            is_live, prev_center = check_liveness(frame, prev_center)

            if not is_live:
                logger.warning("Liveness check failed (no blink + head move).")
                cv2.imshow("Face Detector", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
                continue

            logger.info("LIVE FACE CONFIRMED — generating embedding.")
            # Reset blink state for next session
            _blink_state["confirmed"] = False
            _blink_state["phase"]     = "OPEN"

            # ── Save face crop as base64 JPEG ─────────────────────
            pil_img  = PILImage.fromarray(
                cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            )
            buffered = BytesIO()
            pil_img.save(buffered, format="JPEG")
            face_base64 = base64.b64encode(buffered.getvalue()).decode()

            # ── Generate FaceNet embedding ────────────────────────
            face_tensor = preprocess_face(face_image)

            with torch.no_grad():
                embedding = inception_resnet(face_tensor)

            embedding        = embedding.cpu().numpy().flatten()
            embedding_base64 = base64.b64encode(embedding.tobytes()).decode()

            # ── Clean up and return ───────────────────────────────
            # Release camera BEFORE returning — do not leave it locked
            cap.release()
            cv2.destroyAllWindows()

            return {
                "message":          "Face Detected",
                "image_base64":     face_base64,
                "embedding_base64": embedding_base64,
            }

            # NOTE: cv2.imshow / waitKey below the return is intentionally
            # removed — it was dead code in the original and never executed.

    except Exception as e:
        logger.error(f"faceDetection error: {e}", exc_info=True)

    finally:
        # Guaranteed cleanup even if an exception was raised
        if cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()

    return None


# ─────────────────────────────────────────────
#  Standalone run
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os
    os.environ["QT_QPA_PLATFORM"] = "xcb"   # Ubuntu/Wayland fix

    result = faceDetection()
    if result:
        logger.info(f"Detection complete: {result['message']}")
        logger.info(f"Embedding length  : {len(result['embedding_base64'])} chars (base64)")
    else:
        logger.error("Detection failed.")