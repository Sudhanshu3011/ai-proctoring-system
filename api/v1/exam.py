"""
api/v1/exam.py  — FINAL (uses state.py, no circular import)

Exam Management Endpoints:
  POST /api/v1/exams/create
  GET  /api/v1/exams/
  GET  /api/v1/exams/{exam_id}
  POST /api/v1/exams/{exam_id}/start
  POST /api/v1/exams/{exam_id}/submit
  POST /api/v1/exams/{exam_id}/terminate
"""

import logging
from datetime import datetime, timezone
from fastapi  import APIRouter, Depends, HTTPException, status, BackgroundTasks
from requests import session
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing   import Optional

from core.security import get_current_user_payload, require_role
from db import session
from db.session    import get_db, SessionLocal
from db.models     import (
    User, Exam, ExamSession, RiskScore, Violation,
    ExamStatus, SessionStatus, RiskLevel, UserRole,
)
from services.alert_service import maybe_alert
from ai_engine.risk_engine.integrity_scorer import integrity_scorer

# ── Shared state (no circular import) ────────────────────────────
from api.v1.state import _active_scorers, _active_workers, _active_gaze_trackers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exams", tags=["Exam Management"])


# ─────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────
class ExamCreateRequest(BaseModel):
    title:                    str            = Field(..., min_length=3, max_length=200)
    description:              Optional[str]  = None
    duration_minutes:         int            = Field(60, ge=5, le=300)
    risk_terminate_threshold: Optional[int]  = Field(None, ge=50, le=100)

    model_config = {"json_schema_extra": {"example": {
        "title": "Python Midterm Exam",
        "duration_minutes": 90,
    }}}


class ExamResponse(BaseModel):
    id:               str
    title:            str
    description:      Optional[str]
    duration_minutes: int
    status:           str
    created_by:       str


class StartExamResponse(BaseModel):
    session_id:  str
    exam_id:     str
    message:     str
    started_at:  str


class SubmitExamResponse(BaseModel):
    session_id:   str
    message:      str
    final_score:  float
    risk_level:   str
    submitted_at: str

class RoomScanRequest(BaseModel):
    frames    : list[str] = Field(..., min_length=5, description="Base64 JPEG frames")
    session_id: str
 
 
class RoomScanResponse(BaseModel):
    passed          : bool
    scan_duration_s : float
    frames_analysed : int
    findings        : list
    overall_message : str
 

# ─────────────────────────────────────────────
#  POST /exams/create  (admin only)
# ─────────────────────────────────────────────
@router.post(
    "/create",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new exam (admin only)",
)
def create_exam(
    payload    : ExamCreateRequest,
    token_data : dict    = Depends(require_role("admin")),
    db         : Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    exam = Exam(
        title                    = payload.title,
        description              = payload.description,
        duration_minutes         = payload.duration_minutes,
        status                   = ExamStatus.SCHEDULED,
        risk_terminate_threshold = payload.risk_terminate_threshold,
        created_by               = user.id,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    logger.info(f"Exam created: '{exam.title}' by {user.email}")
    return ExamResponse(
        id               = exam.id,
        title            = exam.title,
        description      = exam.description,
        duration_minutes = exam.duration_minutes,
        status           = exam.status.value,
        created_by       = user.id,
    )


# ─────────────────────────────────────────────
#  GET /exams/
# ─────────────────────────────────────────────
@router.get("/", summary="List all available exams")
def list_exams(
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    exams = db.query(Exam).filter(
        Exam.status != ExamStatus.TERMINATED
    ).all()
    return [
        {
            "id"              : e.id,
            "title"           : e.title,
            "duration_minutes": e.duration_minutes,
            "status"          : e.status.value,
        }
        for e in exams
    ]


# ─────────────────────────────────────────────
#  GET /exams/{exam_id}
# ─────────────────────────────────────────────
@router.get("/{exam_id}", summary="Get exam details")
def get_exam(
    exam_id    : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    return {
        "id"              : exam.id,
        "title"           : exam.title,
        "description"     : exam.description,
        "duration_minutes": exam.duration_minutes,
        "status"          : exam.status.value,
    }


# ─────────────────────────────────────────────
#  POST /exams/{exam_id}/start
# ─────────────────────────────────────────────
@router.post(
    "/{exam_id}/start",
    response_model=StartExamResponse,
    summary="Start exam — creates session and launches monitoring",
)
def start_exam(
    exam_id          : str,
    background_tasks : BackgroundTasks,
    token_data       : dict    = Depends(get_current_user_payload),
    db               : Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    if exam.status == ExamStatus.TERMINATED:
        raise HTTPException(400, "Exam is no longer available")

    # Check face enrolled
    if not user.face_embedding:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Face not enrolled. Complete face enrollment before starting exam."
        )

    # No duplicate active session
    existing = db.query(ExamSession).filter(
        ExamSession.user_id == user.id,
        ExamSession.exam_id == exam_id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if existing:
        raise HTTPException(409, "You already have an active session for this exam")

    # Create session
    now     = datetime.now(timezone.utc)
    session = ExamSession(
        user_id      = user.id,
        exam_id      = exam_id,
        status       = SessionStatus.ACTIVE,
        started_at   = now,
        face_verified = False,
    )
    db.add(session)
    db.flush()

    # Create RiskScore row
    risk_record = RiskScore(
        session_id    = session.id,
        current_score = 0.0,
        risk_level    = RiskLevel.SAFE,
    )
    db.add(risk_record)
    db.commit()
    db.refresh(session)

    # Create RiskScorer
    from ai_engine.risk_engine.scoring import RiskScorer
    scorer = RiskScorer(session_id=session.id)
    _active_scorers[session.id] = scorer

    # Create VideoWorker with its OWN session (not the request-scoped one)
    from workers.video_worker import VideoWorker
    worker_db = SessionLocal()          # independent session — lives with worker
    worker    = VideoWorker(
        session_id = session.id,
        user_id    = user.id,
        scorer     = scorer,
        db_session = worker_db,
    )

    _active_workers[session.id] = worker
    background_tasks.add_task(worker.start)

    logger.info(
        f"Exam started | session={session.id} "
        f"user={user.email} exam='{exam.title}'"
    )
    return StartExamResponse(
        session_id = session.id,
        exam_id    = exam_id,
        message    = "Exam started. Monitoring is active.",
        started_at = now.isoformat(),
    )


# ─────────────────────────────────────────────
#  POST /exams/{exam_id}/submit
# ─────────────────────────────────────────────
@router.post(
    "/{exam_id}/submit",
    response_model=SubmitExamResponse,
    summary="Candidate submits exam normally",
)
def submit_exam(
    exam_id    : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    session = db.query(ExamSession).filter(
        ExamSession.user_id == user.id,
        ExamSession.exam_id == exam_id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(404, "No active session found for this exam")

    return _close_session(session, "COMPLETED", db)


# ─────────────────────────────────────────────
#  POST /exams/{exam_id}/terminate
# ─────────────────────────────────────────────
@router.post(
    "/{exam_id}/terminate",
    summary="Force-terminate exam (admin or risk engine)",
)
def terminate_exam(
    exam_id    : str,
    session_id : str,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(
        ExamSession.id      == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(404, "Active session not found")

    return _close_session(session, "TERMINATED", db)

@router.post(
    "/{exam_id}/room-scan",
    response_model=RoomScanResponse,
    summary="Analyse pre-exam room scan frames",
)
def room_scan(
    exam_id    : str,
    payload    : RoomScanRequest,
    token_data : dict    = Depends(get_current_user_payload),
    db         : Session = Depends(get_db),
):
    """
    Called by RoomScanPage.js after the 15-second camera sweep.
    Decodes all frames, runs RoomScanner, returns pass/fail + findings.
 
    The session must exist and be ACTIVE (was just started by /start).
    """
    import base64
    import numpy as np
    import cv2
    from ai_engine.room_module.room_scan import room_scanner
 
    # Verify session belongs to this user
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")
 
    session = db.query(ExamSession).filter(
        ExamSession.id      == payload.session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.user_id == user.id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if not session:
        raise HTTPException(404, "Active session not found for this exam and user")
 
    # Decode all frames
    frames = []
    for i, b64 in enumerate(payload.frames):
        try:
            img_bytes = base64.b64decode(b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame     = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is not None:
                frames.append(frame)
        except Exception as e:
            logger.debug(f"Room scan frame {i} decode error: {e}")
 
    if len(frames) < 5:
        return RoomScanResponse(
            passed          = False,
            scan_duration_s = 0.0,
            frames_analysed = len(frames),
            findings        = [],
            overall_message = (
                f"Only {len(frames)} frames decoded. "
                "Ensure your camera is working and try again."
            ),
        )
 
    # Run analysis
    try:
        result = room_scanner.analyse(frames)
    except Exception as e:
        logger.error(f"Room scan analysis error: {e}")
        # Fail open — don't block the exam if analyser crashes
        return RoomScanResponse(
            passed          = True,
            scan_duration_s = 0.0,
            frames_analysed = len(frames),
            findings        = [],
            overall_message = "Room scan could not be completed. Proceeding to exam.",
        )
 
    # Persist the room scan result on the session (optional — if model has field)
    try:
        session.room_scan_passed = result.passed
        db.commit()
    except Exception:
        pass  # field may not exist — non-critical
 
    logger.info(
        f"Room scan | session={payload.session_id[:8]} | "
        f"passed={result.passed} | findings={len(result.findings)} | "
        f"frames={len(frames)}"
    )
 
    return RoomScanResponse(
        passed          = bool(result.passed),
        scan_duration_s = float(result.scan_duration_s),
        frames_analysed = int(result.frames_analysed),
        findings        = [
            {
                "finding_type": str(f.finding_type),
                "severity"    : str(f.severity),
                "message"     : str(f.message),
                "confidence"  : float(f.confidence),
            }
            for f in result.findings
        ],
        overall_message = str(result.overall_message),
    )
 

# ─────────────────────────────────────────────
#  Internal: close session
# ─────────────────────────────────────────────
def _close_session(
    session : ExamSession,
    reason  : str,
    db      : Session,
) -> SubmitExamResponse:
    """
    Shared by submit, terminate, admin terminate, and auto-terminate.
    Stops the worker, finalises the score, generates the report.
    Variables user, exam, violations_list etc. are now properly
    fetched from the DB before being used.
    """
    now = datetime.now(timezone.utc)
 
    # ── Stop worker ───────────────────────────────────────────────
    worker = _active_workers.pop(session.id, None)
    if worker:
        worker.stop()
 
    # ── Final score ───────────────────────────────────────────────
    scorer      = _active_scorers.pop(session.id, None)
    final_score = float(scorer.current_score()) if scorer else 0.0
    final_level = str(scorer.current_level())   if scorer else "SAFE"
 
    # ── End face recognizer session ───────────────────────────────
    try:
        from ai_engine.face_module.recognizer import recognizer
        recognizer.end_session(session.id)
    except Exception as e:
        logger.debug(f"Recognizer end_session: {e}")
 
    # ── Update DB ─────────────────────────────────────────────────
    session.status       = (
        SessionStatus.COMPLETED if reason == "COMPLETED"
        else SessionStatus.TERMINATED
    )
    session.submitted_at = now
 
    risk = db.query(RiskScore).filter(
        RiskScore.session_id == session.id
    ).first()
    if risk:
        risk.current_score = float(final_score)
        risk.risk_level    = RiskLevel(final_level)
 
    db.commit()
 
    # ── Fetch user + exam for alert / integrity ───────────────────
    #  FIX: user and exam were used below but never fetched
    user = db.query(User).filter(User.id == session.user_id).first()
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
 
    # ── Alert service ─────────────────────────────────────────────
    if user and exam:
        try:
            maybe_alert(
                session_id  = session.id,
                user_name   = user.full_name,
                user_email  = user.email,
                exam_title  = exam.title,
                risk_score  = final_score,
                risk_level  = final_level,
                alert_type  = "EXAM_COMPLETED" if reason == "COMPLETED" else "SESSION_TERMINATED",
                detail      = f"Session ended with risk score {final_score:.1f}",
            )
        except Exception as e:
            logger.debug(f"Alert failed (non-critical): {e}")
 
    # ── Integrity assessment ──────────────────────────────────────
    #  FIX: violations_list, gaze_tracker, reverify_count etc. were
    #  undefined — fetch violations from DB, pop gaze tracker safely
    try:
        from api.v1.state import _active_gaze_trackers  # may not exist yet
    except ImportError:
        _active_gaze_trackers = {}
 
    try:
        violations_list = db.query(Violation).filter(
            Violation.session_id == session.id
        ).all()
 
        gaze_tracker    = _active_gaze_trackers.pop(session.id, None)
 
        # Count specific violation types from DB rows
        vtype_counts = {}
        for v in violations_list:
            k = v.violation_type.value if hasattr(v.violation_type, 'value') else str(v.violation_type)
            vtype_counts[k] = vtype_counts.get(k, 0) + 1
 
        duration_secs = (
            (now - session.started_at).total_seconds()
            if session.started_at else 0
        )
        # Handle timezone-naive started_at
        if session.started_at and session.started_at.tzinfo is None:
            from datetime import timezone as tz
            started = session.started_at.replace(tzinfo=tz.utc)
            duration_secs = (now - started).total_seconds()
 
        assessment = integrity_scorer.assess({
            "session_id"          : session.id,
            "duration_seconds"    : float(duration_secs),
            "violations"          : [
                {"violation_type": v.violation_type.value if hasattr(v.violation_type,'value') else str(v.violation_type),
                 "weight": v.weight, "confidence": float(v.confidence or 0)}
                for v in violations_list
            ],
            "peak_risk_score"     : float(final_score),
            "final_risk_score"    : float(final_score),
            "face_verify_score"   : float(getattr(session, 'face_verify_score', None) or 1.0),
            "gaze_summary"        : gaze_tracker.get_session_summary().to_dict() if gaze_tracker else {},
            "reverify_failures"   : int(vtype_counts.get("FACE_MISMATCH", 0)),
            "tab_switches"        : int(vtype_counts.get("TAB_SWITCH", 0)),
            "phone_detected_count": int(vtype_counts.get("PHONE_DETECTED", 0)),
            "speech_count"        : int(vtype_counts.get("SPEECH_BURST", 0) + vtype_counts.get("SUSTAINED_SPEECH", 0)),
            "multi_speaker_count" : int(vtype_counts.get("MULTI_SPEAKER", 0)),
            "was_terminated"      : reason == "TERMINATED",
        })
 
        # Store on session if model supports it (graceful — field may not exist)
        try:
            import json
            session.integrity_assessment = json.dumps(assessment.to_dict())
            db.commit()
        except Exception:
            pass
 
    except Exception as e:
        logger.error(f"Integrity assessment failed (non-critical): {e}")
 
    # ── Auto-generate report ──────────────────────────────────────
    try:
        from services.report_services import report_service
        from api.v1.reports          import _build_session_data
        session_data = _build_session_data(session.id, db)
        report_service.generate(session_data)
        logger.info(f"Report generated | session={session.id}")
    except Exception as e:
        logger.error(f"Report generation failed (non-critical): {e}")
 
    logger.info(f"Session {reason} | id={session.id} | score={final_score} | level={final_level}")
 
    return SubmitExamResponse(
        session_id   = session.id,
        message      = f"Exam {reason.lower()}.",
        final_score  = float(final_score),
        risk_level   = str(final_level),
        submitted_at = now.isoformat(),
    )