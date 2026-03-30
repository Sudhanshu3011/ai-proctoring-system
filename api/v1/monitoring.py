"""
api/v1/monitoring.py  — FINAL (uses state.py, violations commit immediately)

Real-Time Monitoring:
  POST /api/v1/monitoring/frame
  POST /api/v1/monitoring/audio
  POST /api/v1/monitoring/browser-event
  GET  /api/v1/monitoring/session/{id}
  WS   /ws/monitor/{session_id}
"""

import logging
import base64
import time
import asyncio
import numpy as np
import cv2
import mediapipe as mp

from fastapi import (
    APIRouter, Depends, HTTPException,
    WebSocket, WebSocketDisconnect,
)
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing   import Optional

from core.security  import get_current_user_payload
from db.session     import get_db, SessionLocal
from db.models      import (
    ExamSession, Violation, RiskScore,
    SessionStatus, ViolationType, RiskLevel,
)

# ── Shared state ─────────────────────────────────────────────────
from api.v1.state import _active_scorers

# ── AI modules ────────────────────────────────────────────────────
from ai_engine.face_module.detector          import detector as face_detector
from ai_engine.head_pose_module.pose_estimator import PoseEstimator
from ai_engine.object_detector.yolo_detector   import ObjectDetector
from ai_engine.behaviour_module.anomaly_detector import (
    AnomalyDetector, ViolationEvent,
)
from ai_engine.risk_engine.scoring import RiskScorer, RiskSnapshot

logger    = logging.getLogger(__name__)
router    = APIRouter(prefix="/monitoring", tags=["Monitoring"])
ws_router = APIRouter(tags=["WebSocket"])

# ── Per-session AI module instances ───────────────────────────────
_pose_estimators  : dict[str, PoseEstimator]  = {}
_object_detectors : dict[str, ObjectDetector] = {}
_anomaly_detectors: dict[str, AnomalyDetector]= {}
_ws_connections   : dict[str, WebSocket]      = {}


# ─────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────
class FrameRequest(BaseModel):
    session_id : str
    frame      : str = Field(..., description="Base64-encoded JPEG frame")

class AudioRequest(BaseModel):
    session_id     : str
    speech_prob    : float  = Field(..., ge=0.0, le=1.0)
    violation_type : Optional[str] = None
    duration_secs  : float  = 0.0

class BrowserEventRequest(BaseModel):
    session_id : str
    event_type : str

class MonitoringResponse(BaseModel):
    session_id      : str
    violations      : list[str]
    risk_score      : float
    risk_level      : str
    should_warn     : bool
    should_terminate: bool
    status          : str


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def _get_active_session(session_id: str, db: Session) -> ExamSession:
    s = db.query(ExamSession).filter(
        ExamSession.id     == session_id,
        ExamSession.status == SessionStatus.ACTIVE,
    ).first()
    if not s:
        raise HTTPException(404, "Active session not found")
    return s


def _get_scorer(session_id: str) -> RiskScorer:
    scorer = _active_scorers.get(session_id)
    if not scorer:
        raise HTTPException(404, f"No scorer for session {session_id}")
    return scorer


def _decode_frame(frame_b64: str) -> np.ndarray:
    try:
        img_bytes = base64.b64decode(frame_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame     = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("imdecode returned None")
        return frame
    except Exception as e:
        raise HTTPException(400, f"Invalid frame data: {e}")


def _get_modules(session_id: str):
    """Lazily create per-session AI instances."""
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
    """Save a violation and commit immediately — don't wait for request end."""
    try:
        v = Violation(
            session_id      = session_id,
            violation_type  = ViolationType(vtype),
            weight          = weight,
            confidence      = round(confidence, 4),
            duration_secs   = duration,
            description     = description,
            screenshot_path = screenshot,
        )
        db.add(v)
        db.commit()
    except Exception as e:
        logger.error(f"Violation save failed [{vtype}]: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _update_risk_db(db: Session, session_id: str, snap: RiskSnapshot):
    """Sync current risk score to DB row."""
    risk = db.query(RiskScore).filter(
        RiskScore.session_id == session_id
    ).first()
    if not risk:
        return
    try:
        risk.current_score = snap.current_score
        risk.risk_level    = RiskLevel(snap.risk_level)
        risk.face_score    = snap.face_score
        risk.pose_score    = snap.pose_score
        risk.object_score  = snap.object_score
        risk.audio_score   = snap.audio_score
        risk.browser_score = snap.browser_score
        db.commit()
    except Exception as e:
        logger.error(f"Risk DB update failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


async def _ws_push(session_id: str, data: dict):
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
    summary="Process one webcam frame through all AI modules",
)
def process_frame(
    payload    : FrameRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    session = _get_active_session(payload.session_id, db)
    scorer  = _get_scorer(payload.session_id)
    frame   = _decode_frame(payload.frame)
    sid     = payload.session_id

    violations : list[str]           = []
    events     : list[ViolationEvent] = []

    pose_est, obj_det, ano_det = _get_modules(sid)

    # ── Face detection ────────────────────────────────────────────
    try:
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        fd_result = face_detector.detect(mp_image)

        if not fd_result.detections:
            violations.append("FACE_ABSENT")
            events.append(ViolationEvent("FACE_ABSENT", time.time(), 10, 1.0, 0.0, "face"))
            _save_violation(db, sid, "FACE_ABSENT", 10, 1.0)

        elif len(fd_result.detections) > 1:
            violations.append("MULTI_FACE")
            events.append(ViolationEvent("MULTI_FACE", time.time(), 30, 1.0, 0.0, "face"))
            _save_violation(db, sid, "MULTI_FACE", 30, 1.0)

        else:
            # ── Head pose ─────────────────────────────────────────
            try:
                pose_result = pose_est.estimate_pose(frame)
                violation   = pose_est.check_violation(pose_result)
                if violation:
                    violations.append("LOOKING_AWAY")
                    events.append(ViolationEvent(
                        "LOOKING_AWAY", time.time(), 15,
                        pose_result.confidence,
                        violation.duration_seconds, "pose",
                    ))
                    _save_violation(
                        db, sid, "LOOKING_AWAY", 15,
                        pose_result.confidence,
                        violation.duration_seconds,
                        f"Direction: {violation.direction}",
                    )
            except Exception as e:
                logger.debug(f"Pose error: {e}")

            # ── Object detection ──────────────────────────────────
            try:
                detections = obj_det.detect(frame)
                obj_events = obj_det.check_violations(detections, frame)
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
            except Exception as e:
                logger.debug(f"Object detection error: {e}")

    except Exception as e:
        logger.debug(f"Face detection error: {e}")

    # ── Anomaly + risk ────────────────────────────────────────────
    if events:
        ano_det.add_events(events)

    report   = ano_det.analyze()
    snapshot = scorer.update(report)
    _update_risk_db(db, sid, snapshot)

    # ── Auto-terminate ────────────────────────────────────────────
    if snapshot.should_terminate:
        logger.critical(f"AUTO-TERMINATE | session={sid} score={snapshot.current_score}")
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
@router.post("/audio", summary="Process audio violation from VAD")
def process_audio(
    payload    : AudioRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    _get_active_session(payload.session_id, db)
    scorer = _get_scorer(payload.session_id)
    sid    = payload.session_id

    if not payload.violation_type:
        return {"status": "ok", "message": "No violation"}

    _, _, ano_det = _get_modules(sid)
    weight = {
        "SPEECH_BURST"    : 10, "SUSTAINED_SPEECH": 20,
        "MULTI_SPEAKER"   : 30, "WHISPER"          : 8,
    }.get(payload.violation_type, 10)

    event = ViolationEvent(
        payload.violation_type, time.time(),
        weight, payload.speech_prob, payload.duration_secs, "audio",
    )
    ano_det.add_event(event)
    report   = ano_det.analyze()
    snapshot = scorer.update(report)

    _save_violation(
        db, sid, payload.violation_type, weight,
        payload.speech_prob, payload.duration_secs,
    )
    _update_risk_db(db, sid, snapshot)

    return {
        "session_id": sid,
        "violation" : payload.violation_type,
        "risk_score": snapshot.current_score,
        "risk_level": snapshot.risk_level,
    }


# ─────────────────────────────────────────────
#  POST /monitoring/browser-event
# ─────────────────────────────────────────────
@router.post("/browser-event", summary="Log browser monitoring event")
def browser_event(
    payload    : BrowserEventRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    _get_active_session(payload.session_id, db)
    scorer = _get_scorer(payload.session_id)
    sid    = payload.session_id

    weight = {
        "TAB_SWITCH"     : 20, "WINDOW_BLUR"    : 10,
        "FULLSCREEN_EXIT": 15, "COPY_PASTE"     : 20,
    }.get(payload.event_type, 10)

    new_score = scorer.add_violation_direct(
        payload.event_type, confidence=1.0, source_module="browser"
    )

    # ← Always save browser events to DB
    _save_violation(
        db, sid, payload.event_type, weight, 1.0,
        description=f"Browser: {payload.event_type}",
    )

    logger.warning(f"Browser event | {payload.event_type} | session={sid}")
    return {
        "session_id": sid,
        "event_type": payload.event_type,
        "risk_score": new_score,
    }


# ─────────────────────────────────────────────
#  GET /monitoring/session/{session_id}
# ─────────────────────────────────────────────
@router.get("/session/{session_id}", summary="Get current risk state")
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
#  WebSocket /ws/monitor/{session_id}
# ─────────────────────────────────────────────
@ws_router.websocket("/ws/monitor/{session_id}")
async def websocket_monitor(websocket: WebSocket, session_id: str):
    """
    Real-time bidirectional monitoring stream.

    Client → Server:
        {"type":"FRAME",   "data":"<base64>"}
        {"type":"AUDIO",   "data":{"violation":"SPEECH_BURST","prob":0.8}}
        {"type":"BROWSER", "data":{"event":"TAB_SWITCH"}}
        {"type":"PING"}

    Server → Client:
        {"type":"RISK_UPDATE", "score":42.1, "level":"WARNING", ...}
        {"type":"ALERT",       "message":"...","level":"WARNING"}
        {"type":"TERMINATE",   "message":"..."}
        {"type":"PONG"}
    """
    await websocket.accept()
    _ws_connections[session_id] = websocket
    logger.info(f"WS connected | session={session_id}")

    scorer   = _active_scorers.get(session_id)
    _, _, ano_det = _get_modules(session_id)

    # Use own DB session for WS — request session may expire
    ws_db = SessionLocal()

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

            if msg_type == "PING":
                await websocket.send_json({"type": "PONG"})
                continue

            # ── FRAME ─────────────────────────────────────────────
            if msg_type == "FRAME" and scorer:
                try:
                    frame     = _decode_frame(msg.get("data", ""))
                    pose_est  = _pose_estimators.get(session_id)
                    obj_det   = _object_detectors.get(session_id)
                    events    = []

                    # Face check
                    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    fd       = face_detector.detect(mp_image)
                    if not fd.detections:
                        events.append(ViolationEvent(
                            "FACE_ABSENT", time.time(), 10, 1.0, 0.0, "face"
                        ))
                        _save_violation(ws_db, session_id, "FACE_ABSENT", 10, 1.0)
                    elif len(fd.detections) > 1:
                        events.append(ViolationEvent(
                            "MULTI_FACE", time.time(), 30, 1.0, 0.0, "face"
                        ))
                        _save_violation(ws_db, session_id, "MULTI_FACE", 30, 1.0)

                    # Pose check
                    if pose_est:
                        r  = pose_est.estimate_pose(frame)
                        v  = pose_est.check_violation(r)
                        if v:
                            events.append(ViolationEvent(
                                "LOOKING_AWAY", time.time(), 15,
                                r.confidence, v.duration_seconds, "pose",
                            ))
                            _save_violation(
                                ws_db, session_id, "LOOKING_AWAY",
                                15, r.confidence, v.duration_seconds,
                            )

                    # Object check (every 3rd second approx)
                    if obj_det and int(time.time()) % 3 == 0:
                        dets = obj_det.detect(frame)
                        oevs = obj_det.check_violations(dets, frame)
                        for oe in oevs:
                            vt = oe.cls.upper() + "_DETECTED"
                            events.append(ViolationEvent(
                                vt, time.time(), oe.weight, oe.confidence, 0.0, "object"
                            ))
                            _save_violation(
                                ws_db, session_id, vt, oe.weight,
                                oe.confidence, screenshot=oe.frame_path,
                            )

                    if events:
                        ano_det.add_events(events)

                except Exception as e:
                    logger.warning(f"WS frame error: {e}")

            # ── AUDIO ─────────────────────────────────────────────
            elif msg_type == "AUDIO" and scorer:
                data   = msg.get("data", {})
                vtype  = data.get("violation")
                prob   = float(data.get("prob", 0.0))
                if vtype:
                    w = {"SPEECH_BURST":10,"SUSTAINED_SPEECH":20,
                         "MULTI_SPEAKER":30,"WHISPER":8}.get(vtype, 10)
                    ano_det.add_event(ViolationEvent(
                        vtype, time.time(), w, prob, 0.0, "audio"
                    ))
                    _save_violation(ws_db, session_id, vtype, w, prob)

            # ── BROWSER ───────────────────────────────────────────
            elif msg_type == "BROWSER" and scorer:
                event_type = msg.get("data", {}).get("event", "")
                if event_type:
                    w = {"TAB_SWITCH":20,"WINDOW_BLUR":10,
                         "FULLSCREEN_EXIT":15,"COPY_PASTE":20}.get(event_type, 10)
                    scorer.add_violation_direct(
                        event_type, 1.0, source_module="browser"
                    )
                    _save_violation(ws_db, session_id, event_type, w, 1.0)

            # ── Send risk update ───────────────────────────────────
            if scorer and msg_type in ("FRAME", "AUDIO", "BROWSER"):
                report   = ano_det.analyze()
                snapshot = scorer.update(report)
                _update_risk_db(ws_db, session_id, snapshot)

                await websocket.send_json({
                    "type"  : "RISK_UPDATE",
                    **snapshot.to_dict(),
                })

                if snapshot.should_warn:
                    await websocket.send_json({
                        "type"   : "ALERT",
                        "message": (
                            f"Risk level: {snapshot.risk_level}. "
                            f"Score: {snapshot.current_score:.1f}"
                        ),
                        "level"  : snapshot.risk_level,
                    })

                if snapshot.should_terminate:
                    await websocket.send_json({
                        "type"   : "TERMINATE",
                        "message": "Exam terminated due to critical risk level.",
                    })
                    break

    except WebSocketDisconnect:
        logger.info(f"WS disconnected | session={session_id}")
    except Exception as e:
        logger.error(f"WS error | session={session_id} | {e}")
    finally:
        _ws_connections.pop(session_id, None)
        try:
            ws_db.close()
        except Exception:
            pass
        logger.info(f"WS closed | session={session_id}")