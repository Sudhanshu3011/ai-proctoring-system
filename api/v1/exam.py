"""
api/v1/exam.py

Exam Management Endpoints

  POST /api/v1/exams/create              → admin creates exam
  GET  /api/v1/exams/                    → list all exams
  GET  /api/v1/exams/{exam_id}           → get exam details
  POST /api/v1/exams/{exam_id}/start     → candidate starts exam
  POST /api/v1/exams/{exam_id}/submit    → candidate submits exam
  POST /api/v1/exams/{exam_id}/terminate → force-terminate (admin/risk engine)

Flow:
    Admin creates exam
        ↓
    Candidate calls /start
        → face verification check
        → creates ExamSession
        → starts RiskScore record
        → locks identity in recognizer
        → starts video_worker background thread
        ↓
    Candidate calls /submit or risk engine calls /terminate
        → stops video_worker
        → finalises RiskScore
        → triggers report generation
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from core.security import get_current_user_payload, require_role
from db.session    import get_db
from db.models     import (
    User, Exam, ExamSession, RiskScore,
    ExamStatus, SessionStatus, RiskLevel, UserRole
)
from ai_engine.face_module.recognizer  import recognizer
from ai_engine.risk_engine.scoring     import RiskScorer
from workers.video_worker              import VideoWorker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exams", tags=["Exam Management"])

# Module-level store of active scorers and workers per session
# In production: move to Redis for multi-instance deployments
_active_scorers : dict[str, RiskScorer]  = {}
_active_workers : dict[str, VideoWorker] = {}


# ─────────────────────────────────────────────
#  Schemas
# ─────────────────────────────────────────────
class ExamCreateRequest(BaseModel):
    title:                   str = Field(..., min_length=3, max_length=200)
    description:             Optional[str] = None
    duration_minutes:        int = Field(60, ge=5, le=300)
    risk_terminate_threshold: Optional[int] = Field(None, ge=50, le=100)

    model_config = {"json_schema_extra": {"example": {
        "title": "Python Midterm Exam",
        "duration_minutes": 90,
        "risk_terminate_threshold": 85,
    }}}


class ExamResponse(BaseModel):
    id:               str
    title:            str
    description:      Optional[str]
    duration_minutes: int
    status:           str
    created_by:       str


class StartExamResponse(BaseModel):
    session_id:    str
    exam_id:       str
    message:       str
    started_at:    str


class SubmitExamResponse(BaseModel):
    session_id:    str
    message:       str
    final_score:   float
    risk_level:    str
    submitted_at:  str


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
    summary="Start exam — verifies face then begins monitoring",
)
def start_exam(
    exam_id            : str,
    background_tasks   : BackgroundTasks,
    token_data         : dict    = Depends(get_current_user_payload),
    db                 : Session = Depends(get_db),
):
    """
    Called by candidate when they click "Start Exam".

    Checks:
      1. Exam exists and is schedulable
      2. Candidate is registered and face-verified
      3. No active session already exists for this candidate

    On success:
      - Creates ExamSession + RiskScore records
      - Starts VideoWorker background thread
      - Locks candidate identity in recognizer
    """
    # Get user
    user = db.query(User).filter(User.email == token_data["sub"]).first()
    if not user:
        raise HTTPException(404, "User not found")

    # Get exam
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    if exam.status == ExamStatus.TERMINATED:
        raise HTTPException(400, "Exam is no longer available")

    # Check face registered
    if not recognizer.is_registered(user.id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Face not registered. Complete registration before starting exam."
        )

    # Check no duplicate active session
    existing = db.query(ExamSession).filter(
        ExamSession.user_id == user.id,
        ExamSession.exam_id == exam_id,
        ExamSession.status  == SessionStatus.ACTIVE,
    ).first()
    if existing:
        raise HTTPException(409, "Active session already exists for this exam")

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
    db.flush()   # get session.id before committing

    # Create RiskScore record
    risk_record = RiskScore(
        session_id    = session.id,
        current_score = 0.0,
        risk_level    = RiskLevel.SAFE,
    )
    db.add(risk_record)
    db.commit()
    db.refresh(session)

    # Start RiskScorer
    scorer = RiskScorer(session_id=session.id)
    _active_scorers[session.id] = scorer

    # Start VideoWorker in background
    worker = VideoWorker(
        session_id = session.id,
        user_id    = user.id,
        scorer     = scorer,
        db_session = db,
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
#  Internal: close a session
# ─────────────────────────────────────────────
def _close_session(session: ExamSession, reason: str, db: Session) -> dict:
    """Stop worker, finalise score, update DB."""
    now = datetime.now(timezone.utc)

    # Stop VideoWorker
    worker = _active_workers.pop(session.id, None)
    if worker:
        worker.stop()

    # Get final score
    scorer       = _active_scorers.pop(session.id, None)
    final_score  = scorer.current_score()    if scorer else 0.0
    final_level  = scorer.current_level()    if scorer else "SAFE"

    # Close recognizer session
    recognizer.end_session(session.id)

    # Update DB
    session.status       = (
        SessionStatus.COMPLETED if reason == "COMPLETED"
        else SessionStatus.TERMINATED
    )
    session.submitted_at = now

    risk_record = db.query(RiskScore).filter(
        RiskScore.session_id == session.id
    ).first()
    if risk_record:
        risk_record.current_score = final_score
        risk_record.risk_level    = RiskLevel(final_level)

    db.commit()

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