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
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing   import Optional

from core.security import get_current_user_payload, require_role
from db.session    import get_db, SessionLocal
from db.models     import (
    User, Exam, ExamSession, RiskScore, Violation,
    ExamStatus, SessionStatus, RiskLevel, UserRole,
)

# ── Shared state (no circular import) ────────────────────────────
from api.v1.state import _active_scorers, _active_workers

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
    """
    now = datetime.now(timezone.utc)

    # Stop VideoWorker (also closes its own DB session)
    worker = _active_workers.pop(session.id, None)
    if worker:
        worker.stop()

    # Final score
    scorer      = _active_scorers.pop(session.id, None)
    final_score = scorer.current_score() if scorer else 0.0
    final_level = scorer.current_level() if scorer else "SAFE"

    # Close face recognizer session
    try:
        from ai_engine.face_module.recognizer import recognizer
        recognizer.end_session(session.id)
    except Exception as e:
        logger.debug(f"Recognizer end_session: {e}")

    # Update session in DB
    session.status       = (
        SessionStatus.COMPLETED
        if reason == "COMPLETED"
        else SessionStatus.TERMINATED
    )
    session.submitted_at = now

    # Update RiskScore
    risk = db.query(RiskScore).filter(
        RiskScore.session_id == session.id
    ).first()
    if risk:
        risk.current_score = final_score
        risk.risk_level    = RiskLevel(final_level)

    db.commit()

    # Auto-generate report (non-blocking — failure doesn't break submit)
    try:
        from services.report_services import report_service
        from api.v1.reports          import _build_session_data
        session_data = _build_session_data(session.id, db)
        report_service.generate(session_data)
        logger.info(f"Report generated | session={session.id}")
    except Exception as e:
        logger.error(f"Report generation failed (non-critical): {e}")

    logger.info(
        f"Session {reason} | id={session.id} | "
        f"score={final_score} level={final_level}"
    )
    return SubmitExamResponse(
        session_id   = session.id,
        message      = f"Exam {reason.lower()}.",
        final_score  = final_score,
        risk_level   = final_level,
        submitted_at = now.isoformat(),
    )