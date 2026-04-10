"""
workers/video_worker.py

Video Processing Worker — Background Thread

Runs continuously during an exam session in a daemon thread.
Handles everything that needs to happen on a schedule,
independent of API requests from the frontend.

Responsibilities:
    1. Periodic face re-verification    (every 60s)
    2. Head pose monitoring             (every frame, 10–15 FPS)
    3. Object detection                 (every frame, 10–15 FPS)
    4. Risk score → DB sync             (every 5s)
    5. Auto-termination trigger         (when score >= threshold)
    6. Admin alert dispatch             (on level change)

Why a worker instead of just the API endpoint?
    The frontend calls /monitoring/frame when it has a frame.
    But frame submission might stall (bad network, hidden tab).
    The worker ensures monitoring continues REGARDLESS of frontend state.
    It also handles re-verification which the frontend never triggers.

Thread safety:
    - VideoWorker runs on its own daemon thread
    - Communicates results via thread-safe queue
    - DB writes go through a separate session (not shared with API)
"""

import cv2
import time
import logging
import threading
import queue
import numpy as np
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from ai_engine.logger import get_logger
from ai_engine.face_module.recognizer          import recognizer,FaceRecognizer
from ai_engine.head_pose_module.pose_estimator import PoseEstimator
from ai_engine.object_detector.yolo_detector     import ObjectDetector
from ai_engine.behaviour_module.anomaly_detector import (
    AnomalyDetector, ViolationEvent
)
from ai_engine.risk_engine.scoring import RiskScorer, RiskSnapshot
from db.models  import (
    ExamSession, Violation, RiskScore,
    SessionStatus, ViolationType, RiskLevel
)

logger = get_logger("video_worker")


# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────
class WorkerConfig:
    TARGET_FPS            = 10      # process at 10 FPS (not full 30 FPS)
    REVERIFY_INTERVAL_SEC = 60      # re-verify identity every 60 seconds
    DB_SYNC_INTERVAL_SEC  = 5       # write score to DB every 5 seconds
    FRAME_SKIP            = 3       # run object detection every Nth frame
    MAX_QUEUE_SIZE        = 30      # drop frames if queue backs up


# ─────────────────────────────────────────────
#  Worker result passed back to API layer
# ─────────────────────────────────────────────
@dataclass
class WorkerResult:
    snapshot      : RiskSnapshot
    violations    : list[str]
    frame_count   : int
    processing_ms : float


# ─────────────────────────────────────────────
#  VideoWorker
# ─────────────────────────────────────────────
class VideoWorker:
    """
    Background monitoring thread for one exam session.

    Lifecycle:
        worker = VideoWorker(session_id, user_id, scorer, db_session)
        worker.start()      # launches daemon thread, opens camera
        ...exam runs...
        worker.stop()       # signals thread to stop, releases camera

    Results:
        worker.get_latest_snapshot()    # non-blocking, returns last snapshot
        worker.result_queue             # queue of WorkerResult objects
    """

    def __init__(
        self,
        session_id  : str,
        user_id     : str,
        scorer      : RiskScorer,
        db_session  : Session,
        config      : WorkerConfig = None,
    ):
        self.session_id = session_id
        self.user_id    = user_id
        self.scorer     = scorer
        self.db         = db_session
        self.config     = config or WorkerConfig()

        # AI modules — one instance per session
        self.pose_estimator  = PoseEstimator()
        self.object_detector = ObjectDetector()
        self.anomaly_detector = AnomalyDetector()

        # Thread state
        self._running        = False
        self._thread : Optional[threading.Thread] = None
        self._stop_event     = threading.Event()

        # Results
        self.result_queue    : queue.Queue = queue.Queue(
            maxsize=self.config.MAX_QUEUE_SIZE
        )
        self._latest_snapshot: Optional[RiskSnapshot] = None
        self._latest_lock    = threading.Lock()

        # Counters
        self._frame_count         = 0
        self._last_reverify_time  = time.time()
        self._last_db_sync_time   = time.time()
        self._violations_log      : list[str] = []
        
        logger.info(
            f"VideoWorker created | "
            f"session={session_id} | user={user_id}"
        )

    # ─────────────────────────────────────────
    #  Lifecycle
    # ─────────────────────────────────────────
    def start(self):
        """Start the background monitoring thread."""
        if self._running:
            logger.warning(f"Worker already running: {self.session_id}")
            return

        self._running = True
        self._stop_event.clear()
        self._thread  = threading.Thread(
            target = self._run,
            name   = f"VideoWorker-{self.session_id[:8]}",
            daemon = True,
        )
        self._thread.start()
        logger.info(f"VideoWorker started | session={self.session_id}")

    def stop(self):
        """Signal the worker to stop and wait for thread to finish."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info(f"VideoWorker stopped | session={self.session_id}")

    # ─────────────────────────────────────────
    #  Non-blocking result access
    # ─────────────────────────────────────────
    def get_latest_snapshot(self) -> Optional[RiskSnapshot]:
        """Return the most recent RiskSnapshot without blocking."""
        with self._latest_lock:
            return self._latest_snapshot

    # ─────────────────────────────────────────
    #  Main loop
    # ─────────────────────────────────────────
    def _run(self):
        """
        FIXED: No camera opened here.
        Frames arrive via process_external_frame() called from the WebSocket.
        Worker only handles periodic tasks: re-verification timer and DB sync.
        """
        logger.info(f"VideoWorker running (frame-less mode) | session={self.session_id}")

        while self._running and not self._stop_event.is_set():
            now = time.time()

            # Periodic DB sync every 5 seconds
            if (now - self._last_db_sync_time) >= self.config.DB_SYNC_INTERVAL_SEC:
                self._sync_to_db()
                self._last_db_sync_time = now

            time.sleep(1.0)

        logger.info(f"VideoWorker stopped | session={self.session_id}")
    # ─────────────────────────────────────────
    #  Frame processing pipeline
    # ─────────────────────────────────────────
    def _process_frame(self, frame: np.ndarray) -> list[str]:
        """
        Run all AI checks on one frame.
        Returns list of violation type strings found.
        """
        t_start    = time.time()
        violations : list[str]         = []
        events     : list[ViolationEvent] = []

        import mediapipe as mp

        # ── Face detection ────────────────────────────────────────
        try:
            from ai_engine.face_module.detector import detector as fd
            rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            fd_result = fd.detect(mp_image)

            if not fd_result.detections:
                violations.append("FACE_ABSENT")
                events.append(ViolationEvent(
                    "FACE_ABSENT", time.time(), 10, 1.0, 0.0, "face"
                ))
            elif len(fd_result.detections) > 1:
                violations.append("MULTI_FACE")
                events.append(ViolationEvent(
                    "MULTI_FACE", time.time(), 30, 1.0, 0.0, "face"
                ))
        except Exception as e:
            logger.debug(f"Face detection error: {e}")

        # ── Head pose ─────────────────────────────────────────────
        try:
            pose_result = self.pose_estimator.estimate_pose(frame)
            violation   = self.pose_estimator.check_violation(pose_result)
            if violation:
                violations.append("LOOKING_AWAY")
                events.append(ViolationEvent(
                    "LOOKING_AWAY", time.time(), 15,
                    pose_result.confidence,
                    violation.duration_seconds, "pose",
                ))
        except Exception as e:
            logger.debug(f"Pose estimation error: {e}")

        # ── Object detection (every Nth frame — heavier model) ────
        if self._frame_count % self.config.FRAME_SKIP == 0:
            try:
                detections = self.object_detector.detect(frame)
                obj_events = self.object_detector.check_violations(
                    detections, frame
                )
                for e in obj_events:
                    vtype = e.cls.upper() + "_DETECTED"
                    violations.append(vtype)
                    events.append(ViolationEvent(
                        vtype, time.time(), e.weight,
                        e.confidence, 0.0, "object",
                    ))
            except Exception as e:
                logger.debug(f"Object detection error: {e}")

        # ── Anomaly + risk update ─────────────────────────────────
        if events:
            self.anomaly_detector.add_events(events)
            self._violations_log.extend(violations)

            # Save to DB (batch every few seconds via _sync_to_db)
            for vtype in violations:
                try:
                    weight = {
                        "FACE_ABSENT": 10, "MULTI_FACE": 30,
                        "LOOKING_AWAY": 15,
                    }.get(vtype, 10)
                    v = Violation(
                        session_id     = self.session_id,
                        violation_type = ViolationType(vtype),
                        weight         = weight,
                        confidence     = 1.0,
                    )
                    self.db.add(v)
                except Exception:
                    pass

        report   = self.anomaly_detector.analyze()
        snapshot = self.scorer.update(report)

        with self._latest_lock:
            self._latest_snapshot = snapshot

        # Push to result queue (non-blocking)
        result = WorkerResult(
            snapshot      = snapshot,
            violations    = violations,
            frame_count   = self._frame_count,
            processing_ms = round((time.time() - t_start) * 1000, 1),
        )
        try:
            self.result_queue.put_nowait(result)
        except queue.Full:
            pass   # drop oldest — queue is for consumers, not critical path

        # ── Auto-terminate check ──────────────────────────────────
        if snapshot.should_terminate:
            logger.critical(
                f"AUTO-TERMINATE from worker | "
                f"session={self.session_id} | "
                f"score={snapshot.current_score:.1f}"
            )
            self._terminate_session()
            self._running = False

        return violations

    # ─────────────────────────────────────────
    #  Periodic re-verification
    # ─────────────────────────────────────────
    def _do_reverification(self, frame: np.ndarray):
        """
        Compare current face embedding against session-start embedding.
        If mismatch → add high-weight violation to risk engine.
        """
        try:
            from ai_engine.face_module.detector import preprocess_face
            from ai_engine.face_module.detector import inception_resnet
            import torch

            # Crop rough face area from center of frame (fast heuristic)
            h, w = frame.shape[:2]
            margin = 0.2
            x1 = int(w * margin);  x2 = int(w * (1 - margin))
            y1 = int(h * margin);  y2 = int(h * (1 - margin))
            face_crop = frame[y1:y2, x1:x2]

            if face_crop.size == 0:
                return

            face_tensor = preprocess_face(face_crop)
            with torch.no_grad():
                embedding = inception_resnet(face_tensor)
            live_emb = embedding.cpu().numpy().flatten()

            result = recognizer.reverify_session(self.session_id, live_emb)

            if not result.matched:
                logger.warning(
                    f"FACE MISMATCH during exam | "
                    f"session={self.session_id} | "
                    f"sim={result.similarity:.3f}"
                )
                self.anomaly_detector.add_event(ViolationEvent(
                    "FACE_MISMATCH", time.time(), 40,
                    1.0 - result.similarity, 0.0, "face",
                    f"Re-verify failed: sim={result.similarity:.3f}"
                ))
                v = Violation(
                    session_id     = self.session_id,
                    violation_type = ViolationType.FACE_MISMATCH,
                    weight         = 40,
                    confidence     = 1.0 - result.similarity,
                    description    = f"Identity mismatch sim={result.similarity:.3f}",
                )
                self.db.add(v)

        except Exception as e:
            logger.debug(f"Re-verification error: {e}")

    # ─────────────────────────────────────────
    #  DB sync
    # ─────────────────────────────────────────
    def _sync_to_db(self):
        """Flush pending DB writes and update RiskScore row."""
        try:
            snapshot = self.get_latest_snapshot()
            if snapshot:
                risk = self.db.query(RiskScore).filter(
                    RiskScore.session_id == self.session_id
                ).first()
                if risk:
                    risk.current_score = snapshot.current_score
                    risk.risk_level    = RiskLevel(snapshot.risk_level)
            self.db.commit()
        except Exception as e:
            logger.error(f"DB sync error: {e}")
            self.db.rollback()

    # ─────────────────────────────────────────
    #  Auto-terminate
    # ─────────────────────────────────────────
    def _terminate_session(self):
        """Mark session as terminated in DB."""
        try:
            session = self.db.query(ExamSession).filter(
                ExamSession.id == self.session_id
            ).first()
            if session and session.status == SessionStatus.ACTIVE:
                session.status = SessionStatus.TERMINATED
                self.db.commit()
                logger.info(
                    f"Session auto-terminated | id={self.session_id}"
                )
        except Exception as e:
            logger.error(f"Auto-terminate DB error: {e}")
            self.db.rollback()