"""
api/v1/monitoring.py

Real-Time Monitoring Endpoints + WebSocket

  POST /api/v1/monitoring/frame          → process one webcam frame
  POST /api/v1/monitoring/audio          → process audio VAD result
  POST /api/v1/monitoring/browser-event  → tab switch / copy-paste etc.
  GET  /api/v1/monitoring/session/{id}   → get current session risk state
  WS   /ws/monitor/{session_id}          → real-time bidirectional stream

WebSocket message format:
    Client → Server:
        {"type": "FRAME",  "data": "<base64_frame>"}
        {"type": "AUDIO",  "data": {"speech_prob": 0.8}}
        {"type": "BROWSER","data": {"event": "TAB_SWITCH"}}

    Server → Client:
        {"type": "RISK_UPDATE", "score": 42.1, "level": "WARNING", ...}
        {"type": "ALERT",       "message": "Looking away detected"}
        {"type": "TERMINATE",   "message": "Exam terminated — risk too high"}
"""

import logging
import base64
import time
import asyncio
import numpy as np
import cv2
import mediapipe as mp
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from core.security  import get_current_user_payload
from db.session     import get_db
from db.models      import ExamSession, Violation, RiskScore, SessionStatus, ViolationType, RiskLevel

# AI modules
from ai_engine.face_module.detector       import detector     as face_detector
from ai_engine.face_module.recognizer     import recognizer
from ai_engine.head_pose_module.pose_estimator import PoseEstimator
from ai_engine.object_detector.yolo_detector    import ObjectDetector
from ai_engine.behaviour_module.anomaly_detector import (
    AnomalyDetector, ViolationEvent, anomaly_detector
)
from ai_engine.risk_engine.scoring import RiskScorer, RiskSnapshot
from api.v1.exam import _active_scorers

logger    = logging.getLogger(__name__)
router    = APIRouter(prefix="/monitoring", tags=["Monitoring"])
ws_router = APIRouter(tags=["WebSocket"])

# Per-session AI module instances
_pose_estimators  : dict[str, PoseEstimator]  = {}
_object_detectors : dict[str, ObjectDetector] = {}
_anomaly_detectors: dict[str, AnomalyDetector]= {}

# Active WebSocket connections: session_id → WebSocket
_ws_connections: dict[str, WebSocket] = {}


# ─────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────
class FrameRequest(BaseModel):
    session_id  : str
    frame       : str = Field(..., description="Base64-encoded JPEG frame")

    model_config = {"json_schema_extra": {"example": {
        "session_id": "uuid-here",
        "frame": "base64encodedframe=="
    }}}


class AudioRequest(BaseModel):
    session_id  : str
    speech_prob : float = Field(..., ge=0.0, le=1.0)
    violation_type: Optional[str] = None   # SPEECH_BURST | SUSTAINED_SPEECH | etc.
    duration_secs : float = 0.0


class BrowserEventRequest(BaseModel):
    session_id  : str
    event_type  : str   # TAB_SWITCH | WINDOW_BLUR | FULLSCREEN_EXIT | COPY_PASTE

    model_config = {"json_schema_extra": {"example": {
        "session_id": "uuid-here",
        "event_type": "TAB_SWITCH"
    }}}


class MonitoringResponse(BaseModel):
    session_id   : str
    violations   : list[str]
    risk_score   : float
    risk_level   : str
    should_warn  : bool
    should_terminate: bool
    status       : str


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def _get_session(session_id: str, db: Session) -> ExamSession:
    session = db.query(ExamSession).filter(
        ExamSession.id     == session_id,
        ExamSession.status == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(404, "Active session not found")
    return session


def _get_scorer(session_id: str) -> RiskScorer:
    scorer = _active_scorers.get(session_id)
    if not scorer:
        raise HTTPException(404, f"No active scorer for session {session_id}")
    return scorer


def _decode_frame(frame_b64: str) -> np.ndarray:
    """Decode base64 JPEG string to BGR numpy array."""
    try:
        img_bytes = base64.b64decode(frame_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame     = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("cv2.imdecode returned None")
        return frame
    except Exception as e:
        raise HTTPException(400, f"Invalid frame data: {e}")


def _get_or_create_modules(session_id: str):
    """Lazily create per-session AI module instances."""
    if session_id not in _pose_estimators:
        _pose_estimators[session_id]   = PoseEstimator()
    if session_id not in _object_detectors:
        _object_detectors[session_id]  = ObjectDetector()
    if session_id not in _anomaly_detectors:
        _anomaly_detectors[session_id] = AnomalyDetector()

    return (
        _pose_estimators[session_id],
        _object_detectors[session_id],
        _anomaly_detectors[session_id],
    )


def _save_violation(
    db         : Session,
    session_id : str,
    vtype      : str,
    weight     : int,
    confidence : float,
    duration   : float = 0.0,
    description: str   = "",
    screenshot : str   = None,
):
    """Persist a violation to the database."""
    try:
        v = Violation(
            session_id      = session_id,
            violation_type  = ViolationType(vtype),
            weight          = weight,
            confidence      = confidence,
            duration_secs   = duration,
            description     = description,
            screenshot_path = screenshot,
        )
        db.add(v)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save violation {vtype}: {e}")
        db.rollback()


def _update_risk_score_db(
    db         : Session,
    session_id : str,
    snapshot   : RiskSnapshot,
):
    """Update the RiskScore table row for this session."""
    risk = db.query(RiskScore).filter(
        RiskScore.session_id == session_id
    ).first()
    if risk:
        risk.current_score = snapshot.current_score
        risk.risk_level    = RiskLevel(snapshot.risk_level)
        risk.face_score    = snapshot.face_score
        risk.pose_score    = snapshot.pose_score
        risk.object_score  = snapshot.object_score
        risk.audio_score   = snapshot.audio_score
        risk.browser_score = snapshot.browser_score
        try:
            db.commit()
        except Exception as e:
            logger.error(f"DB risk score update failed: {e}")
            db.rollback()


async def _push_ws_update(session_id: str, data: dict):
    """Push a risk update to the WebSocket client if connected."""
    ws = _ws_connections.get(session_id)
    if ws:
        try:
            await ws.send_json(data)
        except Exception:
            _ws_connections.pop(session_id, None)


# ─────────────────────────────────────────────
#  POST /monitoring/frame
# ─────────────────────────────────────────────
@router.post(
    "/frame",
    response_model=MonitoringResponse,
    summary="Process a single webcam frame through all AI modules",
)
def process_frame(
    payload    : FrameRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Called by the frontend every ~100ms with a base64 frame.
    Runs frame through:
        1. Face detector      → FACE_ABSENT, MULTI_FACE
        2. Face recognizer    → FACE_MISMATCH (re-verification)
        3. Head pose          → LOOKING_AWAY
        4. Object detector    → PHONE, BOOK, HEADPHONE
        5. Anomaly detector   → pattern analysis
        6. Risk scorer        → updated 0–100 score

    Returns violations + current risk score.
    """
    session    = _get_session(payload.session_id, db)
    scorer     = _get_scorer(payload.session_id)
    frame      = _decode_frame(payload.frame)
    sid        = payload.session_id
    violations : list[str] = []
    events     : list[ViolationEvent] = []

    pose_est, obj_det, ano_det = _get_or_create_modules(sid)

    # ── 1. Face detection ─────────────────────────────────────────
    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    fd_result = face_detector.detect(mp_image)

    if not fd_result.detections:
        violations.append("FACE_ABSENT")
        events.append(ViolationEvent(
            "FACE_ABSENT", time.time(), 10, 1.0, 0.0, "face"
        ))
        _save_violation(db, sid, "FACE_ABSENT", 10, 1.0)

    elif len(fd_result.detections) > 1:
        violations.append("MULTI_FACE")
        events.append(ViolationEvent(
            "MULTI_FACE", time.time(), 30, 1.0, 0.0, "face"
        ))
        _save_violation(db, sid, "MULTI_FACE", 30, 1.0)

    else:
        # ── 2. Head pose ──────────────────────────────────────────
        pose_result = pose_est.estimate_pose(frame)
        violation   = pose_est.check_violation(pose_result)
        if violation:
            violations.append("LOOKING_AWAY")
            events.append(ViolationEvent(
                "LOOKING_AWAY", time.time(), 15,
                pose_result.confidence, violation.duration_seconds, "pose",
                f"Dir: {violation.direction}"
            ))
            _save_violation(
                db, sid, "LOOKING_AWAY", 15,
                pose_result.confidence, violation.duration_seconds,
                f"Direction: {violation.direction}",
            )

        # ── 3. Object detection ───────────────────────────────────
        detections  = obj_det.detect(frame)
        obj_events  = obj_det.check_violations(detections, frame)
        for e in obj_events:
            vtype = e.cls.upper() + "_DETECTED"
            violations.append(vtype)
            events.append(ViolationEvent(
                vtype, time.time(), e.weight,
                e.confidence, 0.0, "object",
            ))
            _save_violation(
                db, sid, vtype, e.weight, e.confidence,
                screenshot=e.frame_path,
            )

    # ── 4. Anomaly + Risk ─────────────────────────────────────────
    ano_det.add_events(events)
    report   = ano_det.analyze()
    snapshot = scorer.update(report)

    _update_risk_score_db(db, sid, snapshot)

    # ── 5. Auto-terminate if critical ────────────────────────────
    if snapshot.should_terminate:
        logger.critical(
            f"AUTO-TERMINATE | session={sid} | "
            f"score={snapshot.current_score}"
        )
        from api.v1.exam import _close_session
        _close_session(session, "TERMINATED", db)

    return MonitoringResponse(
        session_id       = sid,
        violations       = violations,
        risk_score       = snapshot.current_score,
        risk_level       = snapshot.risk_level,
        should_warn      = snapshot.should_warn,
        should_terminate = snapshot.should_terminate,
        status           = "TERMINATED" if snapshot.should_terminate else "ACTIVE",
    )


# ─────────────────────────────────────────────
#  POST /monitoring/audio
# ─────────────────────────────────────────────
@router.post("/audio", summary="Process audio VAD result from frontend")
def process_audio(
    payload    : AudioRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Called by the frontend when Hybrid VAD detects a violation.
    The VAD runs in the browser (or is polled from vad.py).
    """
    session = _get_session(payload.session_id, db)
    scorer  = _get_scorer(payload.session_id)
    sid     = payload.session_id

    if not payload.violation_type:
        return {"status": "ok", "message": "No violation"}

    _, _, ano_det = _get_or_create_modules(sid)
    weight = {
        "SPEECH_BURST"    : 10,
        "SUSTAINED_SPEECH": 20,
        "MULTI_SPEAKER"   : 30,
        "WHISPER"         :  8,
    }.get(payload.violation_type, 10)

    event = ViolationEvent(
        payload.violation_type, time.time(),
        weight, payload.speech_prob,
        payload.duration_secs, "audio",
    )
    ano_det.add_event(event)
    report   = ano_det.analyze()
    snapshot = scorer.update(report)

    _save_violation(
        db, sid, payload.violation_type, weight,
        payload.speech_prob, payload.duration_secs,
    )
    _update_risk_score_db(db, sid, snapshot)

    return {
        "session_id": sid,
        "violation" : payload.violation_type,
        "risk_score": snapshot.current_score,
        "risk_level": snapshot.risk_level,
    }


# ─────────────────────────────────────────────
#  POST /monitoring/browser-event
# ─────────────────────────────────────────────
@router.post("/browser-event", summary="Log a browser monitoring event")
def browser_event(
    payload    : BrowserEventRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Called by JavaScript listeners in the frontend:
        visibilitychange → TAB_SWITCH
        blur             → WINDOW_BLUR
        fullscreenchange → FULLSCREEN_EXIT
        copy/paste       → COPY_PASTE
    """
    session = _get_session(payload.session_id, db)
    scorer  = _get_scorer(payload.session_id)
    sid     = payload.session_id

    weight = {
        "TAB_SWITCH"     : 20,
        "WINDOW_BLUR"    : 10,
        "FULLSCREEN_EXIT": 15,
        "COPY_PASTE"     : 20,
    }.get(payload.event_type, 10)

    new_score = scorer.add_violation_direct(
        payload.event_type, confidence=1.0, source_module="browser"
    )
    _save_violation(db, sid, payload.event_type, weight, 1.0)

    logger.warning(
        f"Browser event | {payload.event_type} | "
        f"session={sid} | score={new_score}"
    )
    return {
        "session_id" : sid,
        "event_type" : payload.event_type,
        "risk_score" : new_score,
    }


# ─────────────────────────────────────────────
#  GET /monitoring/session/{session_id}
# ─────────────────────────────────────────────
@router.get(
    "/session/{session_id}",
    summary="Get current risk state for a session",
)
def get_session_risk(
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    risk = db.query(RiskScore).filter(
        RiskScore.session_id == session_id
    ).first()
    if not risk:
        raise HTTPException(404, "Risk record not found")

    scorer = _active_scorers.get(session_id)
    return {
        "session_id"      : session_id,
        "current_score"   : risk.current_score,
        "risk_level"      : risk.risk_level.value,
        "cheat_probability": scorer.current_probability() if scorer else 0.0,
        "face_score"      : risk.face_score,
        "pose_score"      : risk.pose_score,
        "object_score"    : risk.object_score,
        "audio_score"     : risk.audio_score,
        "browser_score"   : risk.browser_score,
    }


# ─────────────────────────────────────────────
#  WebSocket  /ws/monitor/{session_id}
# ─────────────────────────────────────────────
ws_router = APIRouter(tags=["WebSocket"])

@ws_router.websocket("/ws/monitor/{session_id}")
async def websocket_monitor(
    websocket  : WebSocket,
    session_id : str,
):
    """
    Real-time bidirectional monitoring stream.

    Client → Server messages:
        {"type": "FRAME",   "data": "<base64>"}
        {"type": "AUDIO",   "data": {"violation": "SPEECH_BURST", "prob": 0.8}}
        {"type": "BROWSER", "data": {"event": "TAB_SWITCH"}}
        {"type": "PING"}

    Server → Client messages:
        {"type": "RISK_UPDATE",  "score": 42.1, "level": "WARNING", ...}
        {"type": "ALERT",        "message": "...", "level": "WARNING"}
        {"type": "TERMINATE",    "message": "Exam terminated"}
        {"type": "PONG"}
    """
    await websocket.accept()
    _ws_connections[session_id] = websocket
    logger.info(f"WebSocket connected | session={session_id}")

    scorer   = _active_scorers.get(session_id)
    _, _, ano_det = _get_or_create_modules(session_id)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=30.0
                )
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "PING"})
                continue

            msg_type = msg.get("type", "")

            # ── PING ─────────────────────────────────────────────
            if msg_type == "PING":
                await websocket.send_json({"type": "PONG"})
                continue

            # ── FRAME ────────────────────────────────────────────
            if msg_type == "FRAME" and scorer:
                frame_b64 = msg.get("data", "")
                try:
                    frame = _decode_frame(frame_b64)
            
                    # Run through all AI modules
                    pose_est = _pose_estimators.get(session_id)
                    obj_det  = _object_detectors.get(session_id)
                    ano_det  = _anomaly_detectors.get(session_id)
            
                    violations = []
                    events     = []
            
                    # Face detection
                    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    fd_result = face_detector.detect(mp_image)
            
                    if not fd_result.detections:
                        events.append(ViolationEvent("FACE_ABSENT", time.time(), 10, 1.0, 0.0, "face"))
                        violations.append("FACE_ABSENT")
                    elif len(fd_result.detections) > 1:
                        events.append(ViolationEvent("MULTI_FACE", time.time(), 30, 1.0, 0.0, "face"))
                        violations.append("MULTI_FACE")
            
                    # Head pose
                    if pose_est:
                        result    = pose_est.estimate_pose(frame)
                        violation = pose_est.check_violation(result)
                        if violation:
                            events.append(ViolationEvent("LOOKING_AWAY", time.time(), 15,
                                result.confidence, violation.duration_seconds, "pose"))
                            violations.append("LOOKING_AWAY")
            
                    # Object detection (every 3rd frame to save CPU)
                    if obj_det and (int(time.time() * 10) % 3 == 0):
                        detections = obj_det.detect(frame)
                        obj_events = obj_det.check_violations(detections, frame)
                        for e in obj_events:
                            vtype = e.cls.upper() + "_DETECTED"
                            events.append(ViolationEvent(vtype, time.time(), e.weight,
                                e.confidence, 0.0, "object"))
                            violations.append(vtype)
            
                    if events and ano_det:
                        ano_det.add_events(events)
            
                except Exception as e:
                    logger.warning(f"WS frame processing error: {e}")

            # ── AUDIO ────────────────────────────────────────────
            elif msg_type == "AUDIO" and scorer:
                data       = msg.get("data", {})
                vtype      = data.get("violation")
                prob       = data.get("prob", 0.0)
                if vtype:
                    weight = {"SPEECH_BURST": 10, "SUSTAINED_SPEECH": 20,
                              "MULTI_SPEAKER": 30, "WHISPER": 8}.get(vtype, 10)
                    ano_det.add_event(ViolationEvent(
                        vtype, time.time(), weight, prob, 0.0, "audio"
                    ))

            # ── BROWSER EVENT ─────────────────────────────────────
            elif msg_type == "BROWSER" and scorer:
                event_type = msg.get("data", {}).get("event", "")
                if event_type:
                    scorer.add_violation_direct(event_type, 1.0, source_module="browser")

            # ── Send risk update after processing ─────────────────
            if scorer and msg_type in ("FRAME", "AUDIO", "BROWSER"):
                report   = ano_det.analyze()
                snapshot = scorer.update(report)
                resp     = {"type": "RISK_UPDATE", **snapshot.to_dict()}
                await websocket.send_json(resp)

                if snapshot.should_warn:
                    await websocket.send_json({
                        "type"   : "ALERT",
                        "message": f"Risk level: {snapshot.risk_level}. "
                                   f"Score: {snapshot.current_score:.1f}",
                        "level"  : snapshot.risk_level,
                    })

                if snapshot.should_terminate:
                    await websocket.send_json({
                        "type"   : "TERMINATE",
                        "message": "Exam terminated due to critical risk level.",
                    })
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected | session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error | session={session_id} | {e}")
    finally:
        _ws_connections.pop(session_id, None)
        logger.info(f"WebSocket closed | session={session_id}")